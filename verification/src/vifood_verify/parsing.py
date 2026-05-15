from __future__ import annotations

import json
import re
from typing import Any


JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)
FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def parse_json_object(text: str) -> tuple[dict[str, Any], str]:
    cleaned = FENCE_RE.sub("", text or "").strip()
    try:
        payload = json.loads(cleaned)
        if isinstance(payload, dict):
            return payload, "ok"
    except json.JSONDecodeError:
        pass

    match = JSON_OBJECT_RE.search(cleaned)
    if not match:
        return {}, "unparsed"

    try:
        payload = json.loads(match.group(0))
    except json.JSONDecodeError:
        return {}, "invalid_json"
    if not isinstance(payload, dict):
        return {}, "not_object"
    return payload, "ok_extracted"


def norm_score(value: Any) -> int | None:
    try:
        score = int(value)
    except (TypeError, ValueError):
        return None
    return score if 1 <= score <= 4 else None


def norm_decision(value: Any) -> str | None:
    text = str(value or "").strip().upper()
    return text if text in {"KEEP", "DROP", "REVIEW"} else None


def norm_confidence(value: Any) -> str:
    text = str(value or "").strip().lower()
    return text if text in {"high", "medium", "low"} else "low"


def norm_flags(value: Any) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        value = [value]
    flags = []
    for item in value:
        flag = "_".join(str(item).strip().lower().split())
        if flag:
            flags.append(flag)
    return flags


def norm_triple_reviews(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    reviews = []
    for idx, item in enumerate(value):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status not in {"valid", "invalid", "needs_edit", "unsure"}:
            status = "unsure"
        try:
            triple_index = int(item.get("index", idx))
        except (TypeError, ValueError):
            triple_index = idx
        reviews.append(
            {
                "index": triple_index,
                "status": status,
                "issue": " ".join(str(item.get("issue") or "").split()),
            }
        )
    return sorted(reviews, key=lambda row: row["index"])

