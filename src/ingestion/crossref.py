from __future__ import annotations

from dataclasses import asdict, dataclass
import logging
from pathlib import Path
import re
import time
from typing import Any
import requests

from core.config import Settings
from core.utils import normalize_whitespace, read_json, write_json

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaperRecord:
    paper_id: str
    title: str
    summary: str
    authors: list[str]
    categories: list[str]
    primary_category: str
    published: str
    updated: str
    abs_url: str
    pdf_url: str
    comment: str


def _clean_abstract(raw: str) -> str:
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", "", raw)
    return normalize_whitespace(text)


def _parse_date(item: dict[str, Any], field: str) -> str:
    date_dict = item.get(field, {})
    if isinstance(date_dict, dict):
        date_parts = date_dict.get("date-parts", [])
        if date_parts and date_parts[0]:
            parts = date_parts[0]
            if len(parts) >= 3:
                return f"{parts[0]:04d}-{parts[1]:02d}-{parts[2]:02d}"
            if len(parts) == 2:
                return f"{parts[0]:04d}-{parts[1]:02d}-01"
            if len(parts) == 1:
                return f"{parts[0]:04d}-01-01"
    created = item.get("created", {})
    if isinstance(created, dict):
        created_dt = created.get("date-time", "")
        if created_dt and len(created_dt) >= 10:
            return created_dt[:10]
    return "2026-01-01"


def parse_crossref_payload(payload: dict) -> list[PaperRecord]:
    """Parse Crossref payload thanh list PaperRecord."""
    items = payload.get("message", {}).get("items", [])
    records: list[PaperRecord] = []

    for item in items:
        doi = item.get("DOI", "").strip()
        if not doi:
            continue

        raw_title = item.get("title", [])
        if isinstance(raw_title, list) and raw_title:
            title = str(raw_title[0])
        else:
            title = str(raw_title or "")
        title = normalize_whitespace(re.sub(r"<[^>]+>", "", title))

        raw_abstract = item.get("abstract", "")
        summary = _clean_abstract(raw_abstract)

        authors: list[str] = []
        for author in item.get("author", []):
            given = author.get("given", "").strip()
            family = author.get("family", "").strip()
            name = author.get("name", "").strip()
            if given and family:
                authors.append(f"{given} {family}")
            elif family:
                authors.append(family)
            elif given:
                authors.append(given)
            elif name:
                authors.append(name)
        if not authors:
            authors = ["Unknown Author"]

        categories = item.get("subject", [])
        if not categories or not isinstance(categories, list):
            categories = ["General"]
        primary_category = categories[0] if categories else "General"

        published = _parse_date(item, "published")
        updated = _parse_date(item, "updated") or published

        abs_url = item.get("URL") or f"https://doi.org/{doi}"
        pdf_url = abs_url
        if "link" in item and isinstance(item["link"], list):
            for link in item["link"]:
                if link.get("content-type") == "application/pdf" and link.get("URL"):
                    pdf_url = link["URL"]
                    break

        comment = f"Crossref record {doi}"

        records.append(
            PaperRecord(
                paper_id=doi,
                title=title,
                summary=summary,
                authors=authors,
                categories=categories,
                primary_category=primary_category,
                published=published,
                updated=updated,
                abs_url=abs_url,
                pdf_url=pdf_url,
                comment=comment,
            )
        )
    return records


def fetch_source_records(settings: Settings) -> list[PaperRecord]:
    """Goi source API, luu raw response, parse thanh records co offline fallback."""
    payload: dict | None = None

    if settings.refresh_source:
        url = "https://api.crossref.org/works"
        params = {
            "query": settings.source_query,
            "filter": settings.source_filter,
            "rows": settings.max_results,
        }
        headers = {"User-Agent": "VinUni-DataPipeline-Day10/1.0 (mailto:student@vinuni.edu.vn)"}

        for attempt in range(3):
            try:
                resp = requests.get(url, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    payload = resp.json()
                    break
                logger.warning("API returned status %d on attempt %d", resp.status_code, attempt + 1)
            except Exception as e:
                logger.warning("Failed to fetch from API on attempt %d: %s", attempt + 1, e)
            time.sleep(1)

    # Fallback to local snapshot if API was not requested or failed
    if payload is None:
        if settings.paths.raw_api_response.exists():
            payload = read_json(settings.paths.raw_api_response)
        elif settings.paths.raw_records_json.exists():
            return load_raw_records(settings.paths.raw_records_json)
        else:
            raise FileNotFoundError(f"Missing snapshot at {settings.paths.raw_api_response}")

    # Preserve raw payload
    write_json(settings.paths.raw_api_response, payload)

    # Parse and preserve raw records
    records = parse_crossref_payload(payload)
    write_json(settings.paths.raw_records_json, [asdict(r) for r in records])
    return records


def load_raw_records(path: Path) -> list[PaperRecord]:
    """Doc JSON snapshot va map thanh `PaperRecord`."""
    data = read_json(path)
    records: list[PaperRecord] = []
    for item in data:
        records.append(
            PaperRecord(
                paper_id=item["paper_id"],
                title=item["title"],
                summary=item["summary"],
                authors=item.get("authors", []),
                categories=item.get("categories", []),
                primary_category=item.get("primary_category", "General"),
                published=item.get("published", ""),
                updated=item.get("updated", item.get("published", "")),
                abs_url=item.get("abs_url", ""),
                pdf_url=item.get("pdf_url", ""),
                comment=item.get("comment", ""),
            )
        )
    return records
