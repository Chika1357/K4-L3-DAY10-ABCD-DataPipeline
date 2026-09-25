from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import write_json


def corrupt_clean_dataframe(df: pd.DataFrame, output_log_path: str | Path) -> pd.DataFrame:
    """Simulate 6 dang data corruption thuc te va ghi log."""
    if df.empty:
        write_json(Path(output_log_path), {"corruptions": []})
        return df.copy()

    corrupted = df.copy()
    log_entries: list[dict[str, Any]] = []

    # 1. Drop latest records (bỏ 20% bản ghi mới nhất)
    corrupted = corrupted.sort_values(by="published", ascending=False).reset_index(drop=True)
    n_drop = max(1, int(len(corrupted) * 0.20))
    dropped_ids = corrupted.iloc[:n_drop]["paper_id"].tolist()
    corrupted = corrupted.iloc[n_drop:].reset_index(drop=True)
    log_entries.append(
        {
            "corruption_type": "drop_latest_records",
            "count": n_drop,
            "affected_paper_ids": dropped_ids,
            "description": f"Dropped {n_drop} latest papers (20%) to simulate ingestion data loss",
        }
    )

    # 2. Blank summary (xóa rỗng tóm tắt ở một số dòng)
    blank_indices = [0, 1] if len(corrupted) >= 2 else [0]
    blank_ids = corrupted.iloc[blank_indices]["paper_id"].tolist()
    for idx in blank_indices:
        corrupted.at[idx, "summary"] = ""
    log_entries.append(
        {
            "corruption_type": "blank_summary",
            "count": len(blank_ids),
            "affected_paper_ids": blank_ids,
            "description": "Emptied summary text to simulate failed scraping/extraction",
        }
    )

    # 3. Inject noise (chèn ký tự rác vô nghĩa vào tóm tắt)
    noise_indices = [2, 3] if len(corrupted) >= 4 else [0]
    noise_ids = corrupted.iloc[noise_indices]["paper_id"].tolist()
    noise_str = " ##$$!! ERR_CORRUPT_SEGMENT 0xDEADBEEF @@&&%% "
    for idx in noise_indices:
        current_summary = corrupted.at[idx, "summary"]
        corrupted.at[idx, "summary"] = noise_str + str(current_summary) + noise_str
    log_entries.append(
        {
            "corruption_type": "inject_noise",
            "count": len(noise_ids),
            "affected_paper_ids": noise_ids,
            "description": "Injected random garbage noise tokens into summary",
        }
    )

    # 4. Truncate title (cắt ngắn tiêu đề xuống < 8 ký tự)
    truncate_indices = [4, 5] if len(corrupted) >= 6 else [0]
    truncate_ids = corrupted.iloc[truncate_indices]["paper_id"].tolist()
    for idx in truncate_indices:
        corrupted.at[idx, "title"] = "Paper"
    log_entries.append(
        {
            "corruption_type": "truncate_title",
            "count": len(truncate_ids),
            "affected_paper_ids": truncate_ids,
            "description": "Truncated paper title to '< 8 chars' (Paper)",
        }
    )

    # 5. Stale date (lùi ngày xuất bản về 365 ngày trước để vi phạm Freshness SLA)
    stale_count = min(8, len(corrupted))
    stale_indices = list(range(len(corrupted) - stale_count, len(corrupted)))
    stale_ids = corrupted.iloc[stale_indices]["paper_id"].tolist()
    for idx in stale_indices:
        try:
            old_dt = pd.to_datetime(corrupted.at[idx, "published"]) - timedelta(days=365)
            corrupted.at[idx, "published"] = old_dt.strftime("%Y-%m-%d")
        except Exception:
            corrupted.at[idx, "published"] = "2024-01-01"
    log_entries.append(
        {
            "corruption_type": "stale_date",
            "count": len(stale_ids),
            "affected_paper_ids": stale_ids,
            "description": "Pushed published date back by 365 days to simulate stale data SLA breach",
        }
    )

    # 6. Duplicate rows (nhân bản dòng dữ liệu để vi phạm tính duy nhất)
    dup_indices = [0, 1] if len(corrupted) >= 2 else [0]
    dup_rows = corrupted.iloc[dup_indices].copy()
    dup_ids = dup_rows["paper_id"].tolist()
    corrupted = pd.concat([corrupted, dup_rows], ignore_index=True)
    log_entries.append(
        {
            "corruption_type": "duplicate_rows",
            "count": len(dup_ids),
            "affected_paper_ids": dup_ids,
            "description": "Duplicated existing rows to violate uniqueness constraints in Vector Store",
        }
    )

    # Rebuild helper columns & text_for_embedding
    today = datetime.now(UTC).date()
    corrupted["summary_chars"] = corrupted["summary"].astype(str).str.len()

    def calc_age(pub_str: str) -> int:
        try:
            return max(0, (today - pd.to_datetime(pub_str).date()).days)
        except Exception:
            return 365

    corrupted["age_days"] = corrupted["published"].apply(calc_age)
    corrupted["text_for_embedding"] = (
        "Title: "
        + corrupted["title"].astype(str)
        + "\nAuthors: "
        + corrupted["authors_joined"].astype(str)
        + "\nPublished: "
        + corrupted["published"].astype(str)
        + "\nCategories: "
        + corrupted["categories_joined"].astype(str)
        + "\nSummary: "
        + corrupted["summary"].astype(str)
    )

    # Ghi log ra file output_log_path
    write_json(
        Path(output_log_path),
        {
            "total_corruptions": len(log_entries),
            "original_rows": len(df),
            "corrupted_rows": len(corrupted),
            "corruptions": log_entries,
        },
    )

    return corrupted
