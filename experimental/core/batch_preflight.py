"""
batch_preflight.py — Run BACOWR preflight in bulk.

Usage:
    python batch_preflight.py jobs.csv --output-dir ./preflights

Produces:
    preflights/job_001.json
    preflights/job_002.json
    ...
    preflights/batch_manifest.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

def _to_primitive(value: Any) -> Any:
    """Recursively convert dataclasses/enums/datetimes into JSON-safe values."""
    if is_dataclass(value):
        return _to_primitive(asdict(value))
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): _to_primitive(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_to_primitive(v) for v in value]
    return value


def _serialize_probe_plan(plan: Any) -> Dict[str, Any]:
    """Serialize TargetIntentProfile into a stable JSON contract."""
    return {
        "target_url": plan.target_url,
        "meta_title": plan.meta_title,
        "meta_description": plan.meta_description,
        "head_entity": plan.head_entity,
        "cluster_query": plan.cluster_query,
        "meta_desc_predicate": plan.meta_desc_predicate,
        "probes_completed": plan.probes_completed,
        "probes": [
            {
                "step": probe.step,
                "step_name": probe.step_name,
                "query": probe.query,
                "purpose": probe.purpose,
                "top_results": [
                    {
                        "position": result.position,
                        "title": result.title,
                        "description": result.meta_description,
                        "url": result.url,
                        "domain": result.domain,
                    }
                    for result in probe.top_results
                ],
            }
            for probe in plan.probes
        ],
        "core_entities": plan.core_entities,
        "cluster_entities": plan.cluster_entities,
        "lsi_terms": plan.lsi_terms,
        "entities_to_weave": plan.entities_to_weave,
        "ideal_bridge_direction": plan.ideal_bridge_direction,
        "confidence": plan.confidence,
    }


def _build_preflight_job_payload(preflight: Any, analyzer: TargetIntentAnalyzer) -> Dict[str, Any]:
    """Build one output payload matching the batch preflight contract."""
    job = preflight.job
    target = preflight.target

    probes: Optional[Dict[str, Any]] = None
    status = "needs_metadata"

    if target and target.title and target.title.strip():
        plan = analyzer.build_research_plan_from_metadata(
            url=target.url,
            title=target.title,
            description=target.meta_description or "",
            h1=target.h1 or "",
        )
        probes = _serialize_probe_plan(plan)
        status = "ready_for_serp"

    payload = {
        "job_number": job.job_number,
        "publisher_domain": job.publisher_domain,
        "target_url": job.target_url,
        "anchor_text": job.anchor_text,
        "preflight": {
            "publisher": _to_primitive(preflight.publisher),
            "target": _to_primitive(preflight.target),
            "bridge": _to_primitive(preflight.bridge),
            "language": preflight.language,
            "risk_level": _to_primitive(preflight.risk_level),
            "warnings": list(preflight.warnings or []),
            "generated_at": _to_primitive(preflight.generated_at),
        },
        "probes": probes,
        "status": status,
    }
    return payload


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run Phase 1-4 preflight in batch and persist one JSON per job. "
            "If target metadata is missing, output marks status=needs_metadata."
        ),
        epilog=(
            "Example:\n"
            "  python batch_preflight.py real_textjobs_list.first5.csv --output-dir ./preflights"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("csv_path", help="Path to jobs CSV file.")
    parser.add_argument(
        "--output-dir",
        default="preflights",
        help="Directory where job JSON files + batch_manifest.json are written.",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        raise SystemExit(f"ERROR: CSV not found: {csv_path}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Imported lazily so `--help` stays fast and never bootstraps heavy deps.
    from engine import TargetIntentAnalyzer
    from pipeline import Pipeline, PipelineConfig

    pipe = Pipeline(PipelineConfig())
    jobs = pipe.load_jobs(str(csv_path))
    if not jobs:
        raise SystemExit("ERROR: No valid jobs loaded from CSV.")

    analyzer = TargetIntentAnalyzer()
    all_preflights = asyncio.run(pipe.run_batch_preflight(jobs))

    manifest_jobs: List[Dict[str, Any]] = []
    needs_metadata = 0
    ready_for_serp = 0

    for preflight in all_preflights:
        payload = _build_preflight_job_payload(preflight, analyzer)
        job_number = int(payload["job_number"])
        filename = f"job_{job_number:03d}.json"
        _write_json(output_dir / filename, payload)

        status = payload["status"]
        if status == "needs_metadata":
            needs_metadata += 1
        else:
            ready_for_serp += 1

        manifest_jobs.append(
            {
                "job_number": job_number,
                "file": filename,
                "status": status,
                "has_target_title": bool(
                    ((payload.get("preflight") or {}).get("target") or {}).get("title")
                ),
                "probe_count": len((payload.get("probes") or {}).get("probes", [])),
            }
        )

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source_csv": str(csv_path),
        "output_dir": str(output_dir),
        "total_jobs": len(manifest_jobs),
        "summary": {
            "ready_for_serp": ready_for_serp,
            "needs_metadata": needs_metadata,
        },
        "jobs": sorted(manifest_jobs, key=lambda item: item["job_number"]),
    }
    _write_json(output_dir / "batch_manifest.json", manifest)

    print(f"Batch preflight complete: {len(manifest_jobs)} job(s)")
    print(f"Output directory: {output_dir}")
    print(
        f"Summary: ready_for_serp={ready_for_serp}, needs_metadata={needs_metadata}"
    )


if __name__ == "__main__":
    main()
