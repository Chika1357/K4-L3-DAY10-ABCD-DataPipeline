from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings, normalized_provider
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import EvaluationBundle, evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records, load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex


def _records_for_run(settings: Settings):
    if settings.refresh_source or not settings.paths.raw_records_json.exists():
        return fetch_source_records(settings)
    return load_raw_records(settings.paths.raw_records_json)


def _write_dataframe_artifacts(df, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _ensure_test_set(df, settings: Settings) -> list[dict[str, Any]]:
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        return build_test_set(df, settings.paths.eval_testset)
    return read_json(settings.paths.eval_testset)


def run_baseline_pipeline(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or load_settings()
    run_date = now_utc()

    records = _records_for_run(settings)
    clean_df = build_clean_dataframe(records, run_date)
    _write_dataframe_artifacts(clean_df, settings.paths.clean_csv, settings.paths.clean_json)

    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)

    index = LocalEmbeddingIndex.build(
        clean_df,
        settings=settings,
        embeddings_output_path=settings.paths.embeddings_json,
    )
    test_set = _ensure_test_set(clean_df, settings)
    evaluation: EvaluationBundle = evaluate_pipeline(
        settings=settings,
        index=index,
        test_set_path=settings.paths.eval_testset,
        metrics_output_path=settings.paths.baseline_metrics,
        answers_output_path=settings.paths.baseline_answers,
    )

    source_summary = {
        "source_api": settings.source_api,
        "source_query": settings.source_query,
        "source_filter": settings.source_filter,
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "test_questions": len(test_set),
        "collection_name": index.collection_name,
        "embedding_model": settings.embedding_model,
        "llm_provider": normalized_provider(settings),
        "run_date": run_date.isoformat(),
    }
    generate_phase1_report(
        settings.paths.baseline_report,
        source_summary=source_summary,
        metrics=evaluation.summary,
        quality=quality,
        freshness=freshness,
    )

    demo_answers = []
    for answer in evaluation.answers[:3]:
        demo_answers.append(
            {
                "question": answer["question"],
                "answer": answer["answer"],
                "retrieved_doc_ids": answer["retrieved_doc_ids"],
            }
        )
    write_json(settings.paths.demo_answers, demo_answers)

    return {
        "settings": settings,
        "source_summary": source_summary,
        "quality": quality,
        "freshness": freshness,
        "metrics": evaluation.summary,
        "artifacts": {
            "clean_csv": str(settings.paths.clean_csv),
            "clean_json": str(settings.paths.clean_json),
            "test_set": str(settings.paths.eval_testset),
            "embeddings": str(settings.paths.embeddings_json),
            "baseline_metrics": str(settings.paths.baseline_metrics),
            "baseline_report": str(settings.paths.baseline_report),
        },
    }


def _print_baseline_summary(result: dict[str, Any]) -> None:
    metrics = result["metrics"]
    print("Baseline pipeline complete")
    print(f"- Clean rows: {result['source_summary']['clean_rows']}")
    print(f"- Chroma collection: {result['source_summary']['collection_name']}")
    print(f"- Retrieval hit rate: {metrics.get('retrieval_hit_rate', 0):.3f}")
    print(f"- Mean token F1: {metrics.get('mean_token_f1', 0):.3f}")
    print(f"- Report: {result['artifacts']['baseline_report']}")


def main() -> None:
    """TODO(student): xay dung baseline pipeline end-to-end.

    Pseudo-code:
    1. Load settings.
    2. Load hoac fetch raw records.
    3. Clean data.
    4. Save clean CSV/JSON.
    5. Build Chroma index.
    6. Tao hoac load evaluation set.
    7. Evaluate.
    8. Run quality checks va freshness report.
    9. Tao markdown report.
    10. Co the demo agent tren vai sample question.
    """
    _print_baseline_summary(run_baseline_pipeline())
