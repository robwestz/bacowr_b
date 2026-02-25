"""
integration_test.py — BACOWR v6.2 integration verification.

Run:
    python integration_test.py

This test is designed to validate wiring and invariants, not production SERP quality.
"""

from __future__ import annotations

import asyncio
import warnings

from article_validator import check_trustlinks
from engine import (
    ArticleThesis,
    BridgeRole,
    ConstraintEnforcer,
    ContextBridge,
    SectionPlanner,
    TargetIntentAnalyzer,
    TopicCandidate,
    create_blueprint_from_pipeline,
)
from pipeline import Pipeline, PipelineConfig, PromptGenerator


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _run_preflight_path() -> tuple[Pipeline, object, object]:
    pipe = Pipeline(PipelineConfig())
    jobs = pipe.load_jobs("textjobs_list.csv")
    _assert(len(jobs) >= 1, "Pipeline load_jobs failed: no jobs found")

    preflight = asyncio.run(pipe.run_preflight(jobs[0]))
    _assert(preflight.publisher is not None, "Preflight missing publisher")
    _assert(preflight.target is not None, "Preflight missing target")
    _assert(preflight.bridge is not None, "Preflight missing semantic bridge")

    if not preflight.target.title:
        preflight.target.title = "Fallback Target Title for Integration Test"
    if not preflight.target.meta_description:
        preflight.target.meta_description = "Fallback description for integration coverage."

    return pipe, jobs[0], preflight


def _run_probe_plan(preflight: object) -> object:
    analyzer = TargetIntentAnalyzer()
    plan = analyzer.build_research_plan_from_metadata(
        url=preflight.target.url,
        title=preflight.target.title,
        description=preflight.target.meta_description,
    )
    _assert(len(plan.probes) == 5, "Probe generation must produce exactly 5 probes")
    _assert(all((probe.query or "").strip() for probe in plan.probes), "Empty probe query found")

    # Feed deterministic synthetic SERP data to exercise analysis path without external web_search.
    for idx, probe in enumerate(plan.probes, start=1):
        sample_results = [
            {
                "title": f"{probe.query} guide och analys",
                "description": "Datadriven strategi med kvalitet, resultat och jämförelse.",
                "url": f"https://source{idx}.example.com/deep/link",
            },
            {
                "title": f"Expertöversikt {probe.query}",
                "description": "Fakta, metoder och rekommendationer.",
                "url": f"https://source{idx}.example.org/report/2026",
            },
            {
                "title": f"Så fungerar {probe.query}",
                "description": "Praktiska exempel och fördjupning.",
                "url": f"https://source{idx}.example.net/topic/background",
            },
        ]
        plan = analyzer.analyze_probe_results(plan, idx, sample_results)

    _assert(plan.probes_completed == 5, "Probe analysis did not complete all 5 probes")
    return plan


def _run_blueprint_and_constraints(job: object, preflight: object, plan: object) -> None:
    bp = create_blueprint_from_pipeline(
        job_number=job.job_number,
        publisher_domain=job.publisher_domain,
        target_url=job.target_url,
        anchor_text=job.anchor_text,
        publisher_profile=preflight.publisher,
        target_fingerprint=preflight.target,
        semantic_bridge=preflight.bridge,
    )
    bp.target.intent_profile = plan

    _assert(bp.chosen_topic is not None, "Blueprint missing chosen_topic")
    _assert(len(bp.sections) >= 3, "Blueprint has too few sections")

    targets = [section.target_words for section in bp.sections]
    _assert(targets == [125, 140, 135, 155, 145, 125], f"Unexpected section targets: {targets}")
    _assert(sum(targets) == 825, "Section targets must sum to 825")

    anchor_sections = [s.order for s in bp.sections if s.contains_anchor]
    _assert(anchor_sections == [4], f"Anchor section mismatch: {anchor_sections}")

    # Deterministic planner allocation check (requires explicit primary+supporting bridges).
    planner_sections = SectionPlanner().plan(
        thesis=ArticleThesis(
            statement="test thesis",
            drives_sections=["hook", "anchor"],
            anchor_integration="natural",
        ),
        topic=TopicCandidate(id="integration", topic="integration topic"),
        bridges=[
            ContextBridge(id="b1", concept="c1", search_query="q1", role=BridgeRole.PRIMARY),
            ContextBridge(id="b2", concept="c2", search_query="q2", role=BridgeRole.SUPPORTING),
        ],
        anchor_text=job.anchor_text,
    )
    planner_trust_sections = [s.order for s in planner_sections if s.contains_bridge]
    _assert(
        planner_trust_sections == [2, 3],
        f"SectionPlanner trust section mismatch: {planner_trust_sections}",
    )

    checks = ConstraintEnforcer().check_blueprint(bp)
    by_name = {check.name: check for check in checks}
    _assert(by_name["target_word_count"].passed, "H1 failed (750 <= total <= 900)")
    _assert(by_name["section_floor"].passed, "H1b failed (section floor >=80)")
    _assert(by_name["hook_resolve_band"].passed, "H1c failed (HOOK/RESOLVE in 100-160)")

    prompt = bp.to_agent_prompt()
    _assert(len(prompt) > 200, "Prompt unexpectedly short")
    _assert(
        ("380-430" in prompt) or ("380–430" in prompt),
        "Expected anchor tightening (380-430) missing from prompt",
    )
    _assert(
        "minst 5 SERP-bekräftade entiteter" in prompt,
        "Expected SERP entity tightening (>=5) missing from prompt",
    )


def _run_validator_edge_checks() -> None:
    anchor_text = "lokalvård"
    target_url = "https://www.indoorprofessional.se/tjanster/lokalvard/"
    publisher_domain = "teknikbloggen.se"

    one_trust = (
        "Inledning med kontext [Källa A](https://example.org/report/a).\n\n"
        "Fördjupning med ankare "
        f"[{anchor_text}]({target_url})."
    )
    two_trust = (
        "Kontext [Källa A](https://example.org/report/a) och "
        "[Källa B](https://example.net/guide/b).\n\n"
        "Fördjupning med ankare "
        f"[{anchor_text}]({target_url})."
    )
    zero_trust = f"Bara ankare [{anchor_text}]({target_url})."
    three_trust = (
        "Källor [A](https://a.example.org/x) [B](https://b.example.org/y) "
        "[C](https://c.example.org/z) före ankaret "
        f"[{anchor_text}]({target_url})."
    )

    _assert(check_trustlinks(one_trust, anchor_text, target_url, publisher_domain).passed, "1 trustlink should pass")
    _assert(check_trustlinks(two_trust, anchor_text, target_url, publisher_domain).passed, "2 trustlinks should pass")
    _assert(not check_trustlinks(zero_trust, anchor_text, target_url, publisher_domain).passed, "0 trustlinks should fail")
    _assert(not check_trustlinks(three_trust, anchor_text, target_url, publisher_domain).passed, "3 trustlinks should fail")


def _run_deprecation_checks(pipe: Pipeline) -> None:
    # PromptGenerator.generate deprecation warning
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            PromptGenerator().generate(None)  # warning is emitted before attribute access
        except Exception:
            pass
    _assert(
        any(item.category is DeprecationWarning for item in caught),
        "PromptGenerator.generate did not emit DeprecationWarning",
    )

    # Pipeline.save_prompt deprecation warning
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            pipe.save_prompt(None)  # warning is emitted before preflight dereference
        except Exception:
            pass
    _assert(
        any(item.category is DeprecationWarning for item in caught),
        "Pipeline.save_prompt did not emit DeprecationWarning",
    )


def main() -> None:
    pipe, job, preflight = _run_preflight_path()
    plan = _run_probe_plan(preflight)
    _run_blueprint_and_constraints(job, preflight, plan)
    _run_validator_edge_checks()
    _run_deprecation_checks(pipe)
    print("INTEGRATION TEST PASSED")


if __name__ == "__main__":
    main()
