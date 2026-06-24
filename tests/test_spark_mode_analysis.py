from __future__ import annotations

from scripts.analyze_spark_mode_efficiency import build_summary


def _row(
    *,
    cell_id: str,
    source: str,
    cohort: str,
    reasoning: str,
    mode: str,
    quality: float,
    gpt_tokens: float,
    spark_tokens: float | None,
) -> dict:
    total_tokens = gpt_tokens + (spark_tokens or 0)
    return {
        "cell_id": cell_id,
        "source": source,
        "cohort": cohort,
        "root_reasoning": reasoning,
        "analysis_mode": mode,
        "spark_mode": None if mode == "solo" else mode,
        "status": "partial",
        "quality_score": quality,
        "hidden_correctness": quality,
        "hidden_parity": 1.0,
        "performance": quality,
        "judge": quality,
        "implementation_tokens": total_tokens,
        "gpt55_implementation_tokens": gpt_tokens,
        "spark_implementation_tokens": spark_tokens,
        "quality_per_gpt55_impl_token": quality / gpt_tokens,
        "quality_per_total_impl_token": quality / total_tokens,
        "implementation_elapsed_seconds": 1.0,
        "changed_files": 1.0,
        "production_loc": 10.0,
        "test_loc": 5.0,
    }


def test_summary_keeps_main_and_pilot_spark_groups_separate() -> None:
    summary = build_summary(
        [
            _row(
                cell_id="V3P0_r01",
                source="historical",
                cohort="historical_solo",
                reasoning="low",
                mode="solo",
                quality=0.4,
                gpt_tokens=100.0,
                spark_tokens=None,
            ),
            _row(
                cell_id="SME0_direct_r01",
                source="pilot",
                cohort="spark_assisted",
                reasoning="low",
                mode="direct",
                quality=0.45,
                gpt_tokens=90.0,
                spark_tokens=20.0,
            ),
            _row(
                cell_id="SME0_direct_r02",
                source="main",
                cohort="spark_assisted",
                reasoning="low",
                mode="direct",
                quality=0.5,
                gpt_tokens=80.0,
                spark_tokens=25.0,
            ),
            _row(
                cell_id="SME1_proposal_r01",
                source="main",
                cohort="spark_assisted",
                reasoning="low",
                mode="proposal",
                quality=0.6,
                gpt_tokens=70.0,
                spark_tokens=30.0,
            ),
        ]
    )

    pooled_direct = next(
        group for group in summary["groups"] if group["cohort"] == "spark_assisted" and group["mode"] == "direct"
    )
    main_direct = next(
        group
        for group in summary["phase_groups"]
        if group["cohort"] == "main_spark_assisted" and group["mode"] == "direct"
    )
    pilot_direct = next(
        group
        for group in summary["phase_groups"]
        if group["cohort"] == "pilot_spark_assisted" and group["mode"] == "direct"
    )

    assert pooled_direct["runs"] == 2
    assert main_direct["runs"] == 1
    assert pilot_direct["runs"] == 1
    assert summary["main_direct_vs_proposal"] == [
        {
            "root_reasoning": "low",
            "quality_mean_delta_proposal_minus_direct": 0.1,
            "gpt55_token_mean_delta_proposal_minus_direct": -10.0,
            "spark_token_mean_delta_proposal_minus_direct": 5.0,
            "quality_per_gpt55_token_delta_proposal_minus_direct": 0.002321428571,
        }
    ]
    assert summary["main_spark_vs_historical"][0]["quality_mean_delta_main_minus_historical"] == 0.1
