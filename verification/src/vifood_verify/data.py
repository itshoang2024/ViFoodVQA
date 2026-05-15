from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = {
    "vqa_id",
    "image_id",
    "image",
    "qtype",
    "question",
    "choices",
    "answer",
    "triples_used",
}


@dataclass(frozen=True)
class VQARow:
    row: dict[str, Any]
    split: str
    data_dir: Path

    @property
    def vqa_id(self) -> int:
        return int(self.row["vqa_id"])

    @property
    def image_id(self) -> str:
        return str(self.row["image_id"])

    @property
    def qtype(self) -> str:
        return str(self.row["qtype"])

    @property
    def image_path(self) -> Path:
        return self.data_dir / str(self.row["image"])

    @property
    def choices(self) -> dict[str, str]:
        return {key: str(value) for key, value in self.row["choices"].items()}

    @property
    def triples_used(self) -> list[dict[str, Any]]:
        triples = self.row.get("triples_used") or []
        if isinstance(triples, str):
            triples = json.loads(triples)
        return [dict(triple) for triple in triples]


def load_split(
    data_dir: Path,
    split: str,
    *,
    require_nonempty_triples: bool = True,
) -> list[VQARow]:
    jsonl_path = data_dir / "data" / f"{split}.jsonl"
    if not jsonl_path.exists():
        raise FileNotFoundError(f"Missing split JSONL: {jsonl_path}")

    rows = [VQARow(row=row, split=split, data_dir=data_dir) for row in read_jsonl(jsonl_path)]
    rows = [row for row in rows if not _truthy(row.row.get("is_drop"))]
    if require_nonempty_triples:
        rows = [row for row in rows if row.triples_used]
    validate_rows(rows)
    return rows


def load_splits(
    data_dir: Path,
    splits: Iterable[str],
    *,
    require_nonempty_triples: bool = True,
) -> dict[str, list[VQARow]]:
    return {
        split: load_split(
            data_dir,
            split,
            require_nonempty_triples=require_nonempty_triples,
        )
        for split in splits
    }


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON at {path}:{line_no}") from exc
    return rows


def write_jsonl_row(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, default=str) + "\n")


def validate_rows(rows: list[VQARow]) -> None:
    for item in rows:
        missing = REQUIRED_FIELDS - set(item.row)
        if missing:
            raise ValueError(f"VQA {item.row.get('vqa_id')} missing fields: {sorted(missing)}")
        if set(item.choices) != {"A", "B", "C", "D"}:
            raise ValueError(f"VQA {item.vqa_id} has invalid choices keys")
        if item.row["answer"] not in {"A", "B", "C", "D"}:
            raise ValueError(f"VQA {item.vqa_id} has invalid answer")
        if not item.image_path.exists():
            raise FileNotFoundError(f"Missing image for VQA {item.vqa_id}: {item.image_path}")


def split_summary(rows_by_split: dict[str, list[VQARow]]) -> list[dict[str, Any]]:
    summary = []
    for split, rows in rows_by_split.items():
        summary.append(
            {
                "split": split,
                "rows": len(rows),
                "unique_images": len({row.image_id for row in rows}),
                "qtypes": dict(Counter(row.qtype for row in rows)),
            }
        )
    return summary


def infer_human_decision(row: VQARow, *, assume_test_keep: bool) -> str | None:
    decision = str(row.row.get("verify_decision") or "").strip().upper()
    if decision in {"KEEP", "DROP"}:
        return decision
    if _truthy(row.row.get("is_drop")):
        return "DROP"
    if row.split == "test" and assume_test_keep:
        return "KEEP"
    return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"1", "true", "yes", "y"}

