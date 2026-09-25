from __future__ import annotations

from pathlib import Path
from typing import Any
import pandas as pd

from core.utils import compact_join, first_sentence, write_json


def build_test_set(df: pd.DataFrame, output_path: str | Path) -> list[dict[str, Any]]:
    """Tao bo evaluation set 10 cau hoi tu cleaned dataframe chia deu 4 dang."""
    if df.empty:
        write_json(Path(output_path), [])
        return []

    num_samples = min(10, len(df))
    records = df.to_dict(orient="records")

    # Phan bo 10 cau hoi qua 4 loai: summary (3), authors (3), date (2), categories (2)
    question_plan = [
        ("summary", 0),
        ("summary", 1),
        ("summary", 2),
        ("authors", 3),
        ("authors", 4),
        ("authors", 5),
        ("date", 6),
        ("date", 7),
        ("categories", 8),
        ("categories", 9),
    ]

    test_set: list[dict[str, Any]] = []

    for i, (q_type, idx_plan) in enumerate(question_plan):
        idx = idx_plan % len(records)
        row = records[idx]

        title = row.get("title", "Untitled")
        paper_id = row.get("paper_id", "")
        summary = row.get("summary", "")

        authors_val = row.get("authors_joined") or compact_join(row.get("authors", []), sep=", ")
        categories_val = row.get("categories_joined") or compact_join(row.get("categories", []), sep=", ")
        published_val = str(row.get("published", ""))

        if q_type == "summary":
            question = f"What is the summary of the paper '{title}'?"
            ground_truth = first_sentence(summary)
        elif q_type == "authors":
            question = f"Who authored the paper '{title}'?"
            ground_truth = authors_val
        elif q_type == "date":
            question = f"When was the paper '{title}' published?"
            ground_truth = published_val
        else:  # categories
            question = f"What categories does the paper '{title}' belong to?"
            ground_truth = categories_val

        test_set.append(
            {
                "id": f"eval_{i+1:03d}",
                "question_type": q_type,
                "question": question,
                "ground_truth": ground_truth,
                "ground_truth_doc_ids": [paper_id],
            }
        )

    write_json(Path(output_path), test_set)
    return test_set
