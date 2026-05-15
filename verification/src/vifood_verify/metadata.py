from __future__ import annotations

import json
import os
from collections import Counter
from typing import Any

from .data import VQARow


def enrich_rows_by_split(
    rows_by_split: dict[str, list[VQARow]],
    cfg: dict[str, Any],
) -> dict[str, Any]:
    rows = [row for split_rows in rows_by_split.values() for row in split_rows]
    source = str(cfg.get("source") or "jsonl_embedded").strip().lower()
    lookup_failures: list[str] = []
    image_metadata: dict[str, dict[str, Any]] = {}

    if source == "supabase_image":
        image_metadata = _fetch_supabase_image_rows(rows, cfg, lookup_failures)
    elif source not in {"jsonl_embedded", "none", "off", "disabled"}:
        raise ValueError(f"Unsupported metadata source: {source}")

    for row in rows:
        if source == "supabase_image" and row.image_id in image_metadata:
            _apply_metadata(row, image_metadata[row.image_id], source="supabase_image")
        else:
            _apply_metadata(row, row.row, source="jsonl_embedded")

    return _build_summary(rows, requested_source=source, lookup_failures=lookup_failures)


def _fetch_supabase_image_rows(
    rows: list[VQARow],
    cfg: dict[str, Any],
    lookup_failures: list[str],
) -> dict[str, dict[str, Any]]:
    url_env = str(cfg.get("url_env") or "SUPABASE_URL")
    key_env = str(cfg.get("key_env") or "SUPABASE_KEY")
    url = os.getenv(url_env)
    key = os.getenv(key_env)
    required = bool(cfg.get("required", False))

    if not url or not key:
        message = f"Missing Supabase metadata env var(s): {url_env}, {key_env}"
        if required:
            raise RuntimeError(message)
        lookup_failures.append(message)
        return {}

    try:
        from supabase import create_client
    except ImportError as exc:
        message = "Install the verification package with Supabase support."
        if required:
            raise RuntimeError(message) from exc
        lookup_failures.append(message)
        return {}

    client = create_client(url, key)
    table = str(cfg.get("table") or "image")
    columns = str(cfg.get("columns") or "image_id,food_items,image_desc")
    batch_size = max(1, int(cfg.get("batch_size") or 200))
    image_ids = sorted({row.image_id for row in rows})
    metadata: dict[str, dict[str, Any]] = {}

    for batch in _chunks(image_ids, batch_size):
        try:
            response = client.table(table).select(columns).in_("image_id", batch).execute()
        except Exception as exc:
            message = f"Supabase image metadata lookup failed for batch starting {batch[0]}: {exc}"
            if required:
                raise RuntimeError(message) from exc
            lookup_failures.append(message)
            continue

        for item in response.data or []:
            image_id = str(item.get("image_id") or "").strip()
            if image_id:
                metadata[image_id] = dict(item)

    return metadata


def _apply_metadata(row: VQARow, payload: dict[str, Any], *, source: str) -> None:
    food_items = _normalize_food_items(payload.get("food_items"))
    image_desc = _normalize_text(payload.get("image_desc") or payload.get("image_description"))

    if food_items:
        row.row["food_items"] = food_items
    if image_desc:
        row.row["image_desc"] = image_desc

    missing_fields = []
    if not _normalize_food_items(row.row.get("food_items")):
        missing_fields.append("food_items")
    if not _normalize_text(row.row.get("image_desc") or row.row.get("image_description")):
        missing_fields.append("image_desc")

    row.row["_metadata_source"] = source if not missing_fields else "missing"
    row.row["_metadata_missing_fields"] = missing_fields


def _build_summary(
    rows: list[VQARow],
    *,
    requested_source: str,
    lookup_failures: list[str],
) -> dict[str, Any]:
    missing_food_items = 0
    missing_image_desc = 0
    missing_any = 0
    source_counts: Counter[str] = Counter()

    for row in rows:
        missing_fields = set(row.row.get("_metadata_missing_fields") or [])
        if "food_items" in missing_fields:
            missing_food_items += 1
        if "image_desc" in missing_fields:
            missing_image_desc += 1
        if missing_fields:
            missing_any += 1
        source_counts[str(row.row.get("_metadata_source") or "missing")] += 1

    return {
        "requested_source": requested_source,
        "total_rows": len(rows),
        "unique_image_ids": len({row.image_id for row in rows}),
        "effective_source_counts": dict(sorted(source_counts.items())),
        "metadata_missing_count": missing_any,
        "missing_food_items_count": missing_food_items,
        "missing_image_desc_count": missing_image_desc,
        "lookup_failure_count": len(lookup_failures),
        "lookup_failures": lookup_failures,
    }


def _normalize_food_items(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        if text.startswith("["):
            try:
                loaded = json.loads(text)
            except json.JSONDecodeError:
                return [text]
            return _normalize_food_items(loaded)
        return [text]
    if isinstance(value, (list, tuple)):
        return [text for item in value if (text := _normalize_text(item))]
    return []


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _chunks(items: list[str], size: int) -> list[list[str]]:
    return [items[idx : idx + size] for idx in range(0, len(items), size)]
