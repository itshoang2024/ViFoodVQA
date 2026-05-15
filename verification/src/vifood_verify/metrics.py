from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


def compute_metrics(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    overall = _metric_rows("all", rows)
    for split in sorted({str(row.get("split")) for row in rows}):
        split_rows = [row for row in rows if row.get("split") == split]
        overall.extend(_metric_rows(split, split_rows))

    by_qtype = []
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row.get("split")), str(row.get("qtype")))].append(row)
    for (split, qtype), group in sorted(grouped.items()):
        by_qtype.append(_summary_row(split, qtype, group))
    return overall, by_qtype


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fieldnames: list[str] | None = None) -> None:
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = _fieldnames(rows)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _metric_rows(scope: str, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    summary = _summary_row(scope, "all", rows)
    return [
        {"scope": scope, "metric": "total", "value": summary["total"]},
        {"scope": scope, "metric": "llm_keep", "value": summary["llm_keep"]},
        {"scope": scope, "metric": "llm_drop", "value": summary["llm_drop"]},
        {"scope": scope, "metric": "llm_review", "value": summary["llm_review"]},
        {"scope": scope, "metric": "review_rate", "value": summary["review_rate"]},
        {"scope": scope, "metric": "human_keep", "value": summary["human_keep"]},
        {"scope": scope, "metric": "human_drop", "value": summary["human_drop"]},
        {"scope": scope, "metric": "agreement_rate", "value": summary["agreement_rate"]},
        {"scope": scope, "metric": "false_keep_rate", "value": summary["false_keep_rate"]},
        {"scope": scope, "metric": "false_drop_rate", "value": summary["false_drop_rate"]},
    ]


def _summary_row(split: str, qtype: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    llm_counts = Counter(str(row.get("llm_decision") or "") for row in rows)
    human_counts = Counter(str(row.get("human_decision") or "") for row in rows)

    comparable = [
        row for row in rows
        if row.get("human_decision") in {"KEEP", "DROP"}
        and row.get("llm_decision") in {"KEEP", "DROP"}
    ]
    agreement = sum(1 for row in comparable if row["human_decision"] == row["llm_decision"])
    human_drop = human_counts["DROP"]
    human_keep = human_counts["KEEP"]
    false_keep = sum(
        1 for row in rows
        if row.get("human_decision") == "DROP" and row.get("llm_decision") == "KEEP"
    )
    false_drop = sum(
        1 for row in rows
        if row.get("human_decision") == "KEEP" and row.get("llm_decision") == "DROP"
    )

    return {
        "split": split,
        "qtype": qtype,
        "total": total,
        "llm_keep": llm_counts["KEEP"],
        "llm_drop": llm_counts["DROP"],
        "llm_review": llm_counts["REVIEW"],
        "review_rate": _rate(llm_counts["REVIEW"], total),
        "human_keep": human_keep,
        "human_drop": human_drop,
        "agreement_rate": _rate(agreement, len(comparable)),
        "false_keep_rate": _rate(false_keep, human_drop),
        "false_drop_rate": _rate(false_drop, human_keep),
    }


def _rate(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{numerator / denominator:.6f}"


def _fieldnames(rows: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    return fields

