"""
batch_blueprint.py — Generate blueprints/prompts from enriched preflights.

Usage:
    python batch_blueprint.py ./preflights --output-dir ./blueprints

Requires per-job preflight JSON to have:
    - preflight.target.title (non-empty)
    - probes_completed >= 3 (in probes/target_intent payload)

Produces:
    blueprints/job_001_blueprint.json
    blueprints/job_001_prompt.md
    blueprints/batch_ready.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from engine import (
    SerpProbe,
    SerpSnapshot,
    TargetIntentProfile,
    create_blueprint_from_pipeline,
)
from models import (
    PublisherProfile,
    RiskLevel,
    SemanticBridge,
    SemanticDistance,
    TargetFingerprint,
)


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return datetime.now()
    return datetime.now()


def _parse_semantic_distance(value: Any) -> SemanticDistance:
    raw = str(value or "").lower().strip()
    for item in SemanticDistance:
        if item.value == raw:
            return item
    return SemanticDistance.MODERATE


def _parse_risk_level(value: Any) -> RiskLevel:
    raw = str(value or "").upper().strip()
    for item in RiskLevel:
        if item.value == raw:
            return item
    return RiskLevel.LOW


def _restore_publisher(payload: Dict[str, Any], fallback_domain: str) -> PublisherProfile:
    return PublisherProfile(
        domain=payload.get("domain") or fallback_domain,
        timestamp=_parse_timestamp(payload.get("timestamp")),
        site_name=payload.get("site_name"),
        site_description=payload.get("site_description"),
        primary_language=payload.get("primary_language") or payload.get("language") or "sv",
        primary_topics=list(payload.get("primary_topics") or []),
        secondary_topics=list(payload.get("secondary_topics") or []),
        recent_article_topics=list(payload.get("recent_article_topics") or []),
        category_structure=list(payload.get("category_structure") or []),
        outbound_link_domains=list(payload.get("outbound_link_domains") or []),
        recent_articles=list(payload.get("recent_articles") or []),
        sample_size=int(payload.get("sample_size") or 0),
        confidence=float(payload.get("confidence") or 0.0),
    )


def _restore_target(payload: Dict[str, Any], fallback_url: str) -> TargetFingerprint:
    return TargetFingerprint(
        url=payload.get("url") or fallback_url,
        timestamp=_parse_timestamp(payload.get("timestamp")),
        title=payload.get("title") or "",
        meta_description=payload.get("meta_description") or "",
        h1=payload.get("h1") or "",
        canonical_url=payload.get("canonical_url"),
        language=payload.get("language") or "sv",
        main_keywords=list(payload.get("main_keywords") or []),
        topic_cluster=list(payload.get("topic_cluster") or []),
        internal_links_topics=list(payload.get("internal_links_topics") or []),
        estimated_word_count=int(payload.get("estimated_word_count") or 0),
        has_reviews=bool(payload.get("has_reviews") or False),
        has_pricing=bool(payload.get("has_pricing") or False),
        is_ecommerce=bool(payload.get("is_ecommerce") or False),
    )


def _restore_bridge(
    payload: Optional[Dict[str, Any]],
    publisher_domain: str,
    target_url: str,
    anchor_text: str,
) -> Optional[SemanticBridge]:
    if not payload:
        return None
    return SemanticBridge(
        publisher_domain=payload.get("publisher_domain") or publisher_domain,
        target_url=payload.get("target_url") or target_url,
        anchor_text=payload.get("anchor_text") or anchor_text,
        timestamp=_parse_timestamp(payload.get("timestamp")),
        raw_distance=float(payload.get("raw_distance") or 0.5),
        distance_category=_parse_semantic_distance(payload.get("distance_category")),
        suggestions=[],
        recommended_angle=payload.get("recommended_angle"),
        required_entities=list(payload.get("required_entities") or []),
        forbidden_entities=list(payload.get("forbidden_entities") or []),
        trust_link_topics=list(payload.get("trust_link_topics") or []),
        trust_link_avoid=list(payload.get("trust_link_avoid") or []),
    )


def _restore_intent_profile(payload: Dict[str, Any], target_url: str) -> TargetIntentProfile:
    profile = TargetIntentProfile(target_url=payload.get("target_url") or target_url)
    profile.meta_title = payload.get("meta_title") or ""
    profile.meta_description = payload.get("meta_description") or ""
    profile.head_entity = payload.get("head_entity") or ""
    profile.cluster_query = payload.get("cluster_query") or ""
    profile.meta_desc_predicate = payload.get("meta_desc_predicate") or ""
    profile.confirmed_intent = payload.get("confirmed_intent") or ""
    profile.intent_matches_serp = bool(payload.get("intent_matches_serp") or False)
    profile.intent_gap = payload.get("intent_gap") or ""
    profile.core_entities = list(payload.get("core_entities") or [])
    profile.cluster_entities = list(payload.get("cluster_entities") or [])
    profile.lsi_terms = list(payload.get("lsi_terms") or [])
    profile.competitor_entities = list(payload.get("competitor_entities") or [])
    profile.ta_target_description = payload.get("ta_target_description") or ""
    profile.entities_to_weave = list(payload.get("entities_to_weave") or [])
    profile.entities_to_avoid = list(payload.get("entities_to_avoid") or [])
    profile.ideal_bridge_direction = payload.get("ideal_bridge_direction") or ""
    profile.confidence = float(payload.get("confidence") or 0.0)
    profile.probes_completed = int(payload.get("probes_completed") or 0)

    probes: List[SerpProbe] = []
    for probe_payload in payload.get("probes") or []:
        probe = SerpProbe(
            step=int(probe_payload.get("step") or 0),
            step_name=probe_payload.get("step_name") or "",
            query=probe_payload.get("query") or "",
            purpose=probe_payload.get("purpose") or "",
        )
        top_results = []
        for result_payload in probe_payload.get("top_results") or []:
            top_results.append(
                SerpSnapshot(
                    position=int(result_payload.get("position") or 0),
                    title=result_payload.get("title") or "",
                    meta_description=result_payload.get("description") or "",
                    url=result_payload.get("url") or "",
                    domain=result_payload.get("domain") or "",
                )
            )
        probe.top_results = top_results
        probes.append(probe)
    profile.probes = probes

    if profile.probes and profile.probes_completed == 0:
        profile.probes_completed = sum(1 for probe in profile.probes if probe.top_results)
    return profile


def _readiness(job_payload: Dict[str, Any]) -> Tuple[bool, str]:
    target = ((job_payload.get("preflight") or {}).get("target") or {})
    title = (target.get("title") or "").strip()
    if not title:
        return False, "missing target.title"

    intent = job_payload.get("target_intent") or job_payload.get("probes")
    probes_completed = int((intent or {}).get("probes_completed") or 0)
    if probes_completed < 3:
        return False, f"probes_completed={probes_completed} (<3)"
    return True, "ready"


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Generate ArticleBlueprint + prompt files from enriched preflight JSON files."
        ),
        epilog=(
            "Example:\n"
            "  python batch_blueprint.py ./preflights --output-dir ./blueprints"
        ),
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("preflights_dir", help="Directory containing preflights/job_*.json")
    parser.add_argument(
        "--output-dir",
        default="blueprints",
        help="Directory where blueprints/prompts and batch_ready.json are written.",
    )
    args = parser.parse_args()

    preflights_dir = Path(args.preflights_dir)
    if not preflights_dir.exists():
        raise SystemExit(f"ERROR: Preflight directory not found: {preflights_dir}")

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    job_files = sorted(preflights_dir.glob("job_*.json"))
    if not job_files:
        raise SystemExit(f"ERROR: No job_*.json files found in {preflights_dir}")

    ready_jobs: List[Dict[str, Any]] = []
    skipped_jobs: List[Dict[str, Any]] = []

    for job_file in job_files:
        job_payload = _load_json(job_file)
        is_ready, reason = _readiness(job_payload)
        job_number = int(job_payload.get("job_number") or 0)

        if not is_ready:
            skipped_jobs.append(
                {
                    "job_number": job_number,
                    "file": job_file.name,
                    "reason": reason,
                }
            )
            continue

        preflight_payload = job_payload.get("preflight") or {}
        publisher_payload = preflight_payload.get("publisher") or {}
        target_payload = preflight_payload.get("target") or {}
        bridge_payload = preflight_payload.get("bridge") or {}

        publisher = _restore_publisher(
            publisher_payload, fallback_domain=job_payload.get("publisher_domain") or ""
        )
        target = _restore_target(
            target_payload, fallback_url=job_payload.get("target_url") or ""
        )
        _ = _parse_risk_level(preflight_payload.get("risk_level"))  # kept for contract compatibility
        bridge = _restore_bridge(
            bridge_payload,
            publisher_domain=job_payload.get("publisher_domain") or "",
            target_url=job_payload.get("target_url") or "",
            anchor_text=job_payload.get("anchor_text") or "",
        )

        blueprint = create_blueprint_from_pipeline(
            job_number=job_number,
            publisher_domain=job_payload.get("publisher_domain") or publisher.domain,
            target_url=job_payload.get("target_url") or target.url,
            anchor_text=job_payload.get("anchor_text") or "",
            publisher_profile=publisher,
            target_fingerprint=target,
            semantic_bridge=bridge,
        )

        intent_payload = job_payload.get("target_intent") or job_payload.get("probes")
        if intent_payload:
            blueprint.target.intent_profile = _restore_intent_profile(
                intent_payload, target_url=target.url
            )

        blueprint_filename = f"job_{job_number:03d}_blueprint.json"
        prompt_filename = f"job_{job_number:03d}_prompt.md"

        _write_text(output_dir / blueprint_filename, blueprint.to_json())
        _write_text(output_dir / prompt_filename, blueprint.to_agent_prompt())

        ready_jobs.append(
            {
                "job_number": job_number,
                "source_file": job_file.name,
                "blueprint_file": blueprint_filename,
                "prompt_file": prompt_filename,
                "status": "ready",
            }
        )

    manifest = {
        "generated_at": datetime.now().isoformat(),
        "source_preflights_dir": str(preflights_dir),
        "output_dir": str(output_dir),
        "total_jobs": len(job_files),
        "ready_count": len(ready_jobs),
        "skipped_count": len(skipped_jobs),
        "ready_jobs": sorted(ready_jobs, key=lambda item: item["job_number"]),
        "skipped_jobs": sorted(skipped_jobs, key=lambda item: item["job_number"]),
    }
    _write_text(
        output_dir / "batch_ready.json",
        json.dumps(manifest, indent=2, ensure_ascii=False),
    )

    print(f"Batch blueprint complete: ready={len(ready_jobs)}, skipped={len(skipped_jobs)}")
    print(f"Output directory: {output_dir}")


if __name__ == "__main__":
    main()
