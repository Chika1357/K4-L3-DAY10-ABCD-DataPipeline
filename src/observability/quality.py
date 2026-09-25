from __future__ import annotations

from pathlib import Path
from typing import Any
import great_expectations as gx
import pandas as pd

from core.config import Settings
from core.utils import write_json


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chot kiem dich chat luong du lieu bang Great Expectations 1.x."""
    try:
        context = gx.get_context(mode="ephemeral")
        data_source = context.data_sources.add_pandas(name=f"papers_source_{report_name}")
        data_asset = data_source.add_dataframe_asset(name=f"papers_asset_{report_name}")
        batch_def = data_asset.add_batch_definition_whole_dataframe(f"papers_batch_{report_name}")
        batch = batch_def.get_batch(batch_parameters={"dataframe": df})

        suite = gx.ExpectationSuite(name=f"papers_quality_suite_{report_name}")

        # 1. ExpectTableRowCountToBeBetween (5 - 5000 dong)
        suite.add_expectation(gx.expectations.ExpectTableRowCountToBeBetween(min_value=5, max_value=5000))

        # 2. ExpectColumnValuesToNotBeNull (paper_id, title, text_for_embedding)
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="paper_id"))
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="title"))
        suite.add_expectation(gx.expectations.ExpectColumnValuesToNotBeNull(column="text_for_embedding"))

        # 3. ExpectColumnValuesToBeUnique (paper_id)
        suite.add_expectation(gx.expectations.ExpectColumnValuesToBeUnique(column="paper_id"))

        # 4. ExpectColumnValueLengthsToBeBetween (summary min 30 ky tu)
        suite.add_expectation(gx.expectations.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=30))

        validation_result = batch.validate(suite)

        overall_success = bool(validation_result.success)
        details = []
        for result in validation_result.results:
            details.append(
                {
                    "expectation_type": result.expectation_config.type,
                    "kwargs": result.expectation_config.kwargs,
                    "success": bool(result.success),
                    "result": result.result,
                }
            )

        report = {
            "success": overall_success,
            "report_name": report_name,
            "total_expectations": len(details),
            "passed_expectations": sum(1 for d in details if d["success"]),
            "failed_expectations": sum(1 for d in details if not d["success"]),
            "details": details,
        }
    except Exception as exc:
        # Fallback kiem tra chuan logic neu GX gap loi moi truong
        row_count_ok = 5 <= len(df) <= 5000
        null_ok = (
            df["paper_id"].notna().all()
            and (df["paper_id"].str.strip().str.len() > 0).all()
            and df["title"].notna().all()
            and (df["title"].str.strip().str.len() > 0).all()
            and df["text_for_embedding"].notna().all()
            and (df["text_for_embedding"].str.strip().str.len() > 0).all()
        )
        unique_ok = df["paper_id"].is_unique
        summary_len_ok = (df["summary"].astype(str).str.len() >= 30).all()

        overall_success = bool(row_count_ok and null_ok and unique_ok and summary_len_ok)
        report = {
            "success": overall_success,
            "report_name": report_name,
            "total_expectations": 4,
            "passed_expectations": sum([row_count_ok, null_ok, unique_ok, summary_len_ok]),
            "failed_expectations": 4 - sum([row_count_ok, null_ok, unique_ok, summary_len_ok]),
            "fallback_used": True,
            "error": str(exc),
            "checks": {
                "row_count_between_5_and_5000": bool(row_count_ok),
                "required_columns_not_null": bool(null_ok),
                "paper_id_unique": bool(unique_ok),
                "summary_length_ge_30": bool(summary_len_ok),
            },
        }

    report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    write_json(report_path, report)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop freshness report theo SLA 180 ngay."""
    total_rows = len(df)
    if total_rows == 0:
        report = {
            "total_rows": 0,
            "stale_rows": 0,
            "stale_ratio": 0.0,
            "freshness_threshold_days": settings.freshness_threshold_days,
            "max_stale_ratio_allowed": 0.25,
            "latest_published": None,
            "oldest_published": None,
            "is_fresh": True,
        }
        write_json(Path(report_path), report)
        return report

    threshold = settings.freshness_threshold_days
    stale_rows = int((df["age_days"] > threshold).sum())
    stale_ratio = stale_rows / total_rows
    is_fresh = bool(stale_ratio <= 0.25)

    latest_published = str(df["published"].max()) if "published" in df.columns else None
    oldest_published = str(df["published"].min()) if "published" in df.columns else None

    report = {
        "total_rows": total_rows,
        "stale_rows": stale_rows,
        "stale_ratio": round(stale_ratio, 4),
        "freshness_threshold_days": threshold,
        "max_stale_ratio_allowed": 0.25,
        "latest_published": latest_published,
        "oldest_published": oldest_published,
        "is_fresh": is_fresh,
    }
    write_json(Path(report_path), report)
    return report
