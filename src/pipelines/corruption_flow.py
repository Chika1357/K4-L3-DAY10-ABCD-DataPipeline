from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from pipelines.phase1 import run_baseline_pipeline
from retrieval.index import LocalEmbeddingIndex


def _write_dataframe_artifacts(df: pd.DataFrame, csv_path: Path, json_path: Path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _freshness_path(settings: Settings, label: str) -> Path:
    return settings.paths.quality_dir / f"{label}_freshness_report.json"


def _ensure_baseline(settings: Settings) -> dict[str, Any]:
    required_paths = [
        settings.paths.clean_json,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
    ]
    if all(path.exists() for path in required_paths):
        return read_json(settings.paths.baseline_metrics)

    result = run_baseline_pipeline(settings)
    return result["metrics"]


def _load_repair_records(settings: Settings):
    if settings.paths.raw_records_json.exists():
        return load_raw_records(settings.paths.raw_records_json)
    return fetch_source_records(settings)


def run_corruption_pipeline(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or load_settings()

    baseline_metrics = _ensure_baseline(settings)
    clean_df = pd.read_json(settings.paths.clean_json)

    corrupted_df = corrupt_clean_dataframe(clean_df, settings.paths.corruption_log)
    _write_dataframe_artifacts(
        corrupted_df,
        settings.paths.corrupted_clean_csv,
        settings.paths.corrupted_clean_json,
    )
    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(
        corrupted_df,
        settings,
        _freshness_path(settings, "corrupted"),
    )
    corrupted_index = LocalEmbeddingIndex.build(
        corrupted_df,
        settings=settings,
        embeddings_output_path=settings.paths.corrupted_embeddings_json,
    )
    corrupted_eval = evaluate_pipeline(
        settings=settings,
        index=corrupted_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.corrupted_metrics,
        answers_output_path=settings.paths.corrupted_answers,
    )

    repair_records = _load_repair_records(settings)
    repaired_df = build_clean_dataframe(repair_records, now_utc())
    _write_dataframe_artifacts(
        repaired_df,
        settings.paths.repaired_clean_csv,
        settings.paths.repaired_clean_json,
    )
    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(
        repaired_df,
        settings,
        _freshness_path(settings, "repaired"),
    )
    repaired_index = LocalEmbeddingIndex.build(
        repaired_df,
        settings=settings,
        embeddings_output_path=settings.paths.repaired_embeddings_json,
    )
    repaired_eval = evaluate_pipeline(
        settings=settings,
        index=repaired_index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.repaired_metrics,
        answers_output_path=settings.paths.repaired_answers,
    )

    generate_corruption_report(
        settings.paths.comparison_report,
        baseline_metrics=baseline_metrics,
        corrupted_metrics=corrupted_eval.summary,
        repaired_metrics=repaired_eval.summary,
        corrupted_quality=corrupted_quality,
        repaired_quality=repaired_quality,
        corrupted_freshness=corrupted_freshness,
        repaired_freshness=repaired_freshness,
    )

    return {
        "baseline_metrics": baseline_metrics,
        "corrupted_metrics": corrupted_eval.summary,
        "repaired_metrics": repaired_eval.summary,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corrupted_freshness": corrupted_freshness,
        "repaired_freshness": repaired_freshness,
        "collections": {
            "corrupted": corrupted_index.collection_name,
            "repaired": repaired_index.collection_name,
        },
        "artifacts": {
            "corruption_log": str(settings.paths.corruption_log),
            "corrupted_metrics": str(settings.paths.corrupted_metrics),
            "repaired_metrics": str(settings.paths.repaired_metrics),
            "comparison_report": str(settings.paths.comparison_report),
        },
    }


def _metric_line(label: str, metrics: dict[str, Any]) -> str:
    return (
        f"{label:<10} "
        f"hit_rate={metrics.get('retrieval_hit_rate', 0):.3f} "
        f"token_f1={metrics.get('mean_token_f1', 0):.3f} "
        f"judge={metrics.get('mean_judge_score', 0):.3f}"
    )


def _print_corruption_summary(result: dict[str, Any]) -> None:
    print("Corruption and repair flow complete")
    print(_metric_line("baseline", result["baseline_metrics"]))
    print(_metric_line("corrupted", result["corrupted_metrics"]))
    print(_metric_line("repaired", result["repaired_metrics"]))
    print(f"- Corrupted collection: {result['collections']['corrupted']}")
    print(f"- Repaired collection: {result['collections']['repaired']}")
    print(f"- Report: {result['artifacts']['comparison_report']}")


def main() -> None:
    """TODO(student): xay dung corruption -> evaluate -> repair -> compare flow.

    Pseudo-code:
    1. Load baseline metrics va clean dataset.
    2. Tao corrupted dataframe.
    3. Save corrupted artifacts.
    4. Rebuild index va evaluate.
    5. Run quality checks/freshness tren corrupted data.
    6. Repair lai tu raw records.
    7. Evaluate repaired dataset.
    8. Tao comparison report.
    """
    _print_corruption_summary(run_corruption_pipeline())
