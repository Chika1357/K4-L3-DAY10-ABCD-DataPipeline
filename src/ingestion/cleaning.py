from __future__ import annotations

from datetime import datetime
import re
import pandas as pd

from core.utils import compact_join, normalize_whitespace
from ingestion.crossref import PaperRecord


def _clean_text(value: str) -> str:
    if not value:
        return ""
    text = re.sub(r"<[^>]+>", "", value)
    return normalize_whitespace(text)


def _calculate_age_days(published_str: str, run_date: datetime) -> int:
    try:
        run_d = run_date.date() if isinstance(run_date, datetime) else run_date
        pub_date = pd.to_datetime(published_str).date()
        return max(0, (run_d - pub_date).days)
    except Exception:
        return 0


def build_clean_dataframe(records: list[PaperRecord], run_date: datetime) -> pd.DataFrame:
    """Clean raw records thanh dataframe san sang de embed."""
    rows = []
    for r in records:
        paper_id = r.paper_id.strip() if r.paper_id else ""
        if not paper_id:
            continue

        title = _clean_text(r.title)
        summary = _clean_text(r.summary)
        authors = [normalize_whitespace(a) for a in r.authors if a] or ["Unknown Author"]
        categories = [normalize_whitespace(c) for c in r.categories if c] or ["General"]
        primary_category = categories[0] if categories else "General"
        published = r.published.strip() if r.published else ""
        updated = r.updated.strip() if r.updated else published
        abs_url = r.abs_url.strip() if r.abs_url else f"https://doi.org/{paper_id}"
        pdf_url = r.pdf_url.strip() if r.pdf_url else abs_url
        comment = r.comment.strip() if r.comment else ""

        authors_joined = compact_join(authors, sep=", ")
        categories_joined = compact_join(categories, sep=", ")
        summary_chars = len(summary)
        age_days = _calculate_age_days(published, run_date)

        text_for_embedding = (
            f"Title: {title}\n"
            f"Authors: {authors_joined}\n"
            f"Published: {published}\n"
            f"Categories: {categories_joined}\n"
            f"Summary: {summary}"
        )

        rows.append(
            {
                "paper_id": paper_id,
                "title": title,
                "summary": summary,
                "authors": authors,
                "categories": categories,
                "primary_category": primary_category,
                "published": published,
                "updated": updated,
                "abs_url": abs_url,
                "pdf_url": pdf_url,
                "comment": comment,
                "authors_joined": authors_joined,
                "categories_joined": categories_joined,
                "summary_chars": summary_chars,
                "age_days": age_days,
                "text_for_embedding": text_for_embedding,
            }
        )

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # 1. Khử trùng lặp theo paper_id
    df = df.drop_duplicates(subset=["paper_id"], keep="first")

    # 2. Lọc bỏ các dòng không hợp lệ
    df = df[df["title"].str.strip().str.len() > 0]
    df = df[df["summary"].str.strip().str.len() > 0]

    # 3. Sắp xếp ổn định
    df = df.sort_values(by=["published", "paper_id"], ascending=[False, True]).reset_index(drop=True)

    return df
