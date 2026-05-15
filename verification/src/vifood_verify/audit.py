from __future__ import annotations

import random
from collections import defaultdict
from typing import Any


def build_review_queue(rows: list[dict[str, Any]], *, risk_qtypes: set[str]) -> list[dict[str, Any]]:
    queue = []
    for row in rows:
        human = row.get("human_decision")
        llm = row.get("llm_decision")
        mismatch = human in {"KEEP", "DROP"} and llm in {"KEEP", "DROP"} and human != llm
        if llm != "REVIEW" and not mismatch:
            continue

        flags = row.get("failure_flags") or []
        reason = "human_llm_disagreement" if mismatch else "llm_review"
        priority = _priority(row, flags, risk_qtypes, mismatch=mismatch)
        queue.append(
            {
                "priority": priority,
                "reason": reason,
                "vqa_id": row.get("vqa_id"),
                "image_id": row.get("image_id"),
                "split": row.get("split"),
                "qtype": row.get("qtype"),
                "llm_decision": llm,
                "human_decision": human or "",
                "confidence": row.get("confidence"),
                "failure_flags": ";".join(flags),
                "rationale_short": row.get("rationale_short", ""),
            }
        )
    return sorted(queue, key=lambda item: (item["priority"], item["split"], item["qtype"], item["vqa_id"]))


def build_audit_sample(
    rows: list[dict[str, Any]],
    *,
    sample_size: int,
    seed: int,
    risk_qtypes: set[str],
) -> list[dict[str, Any]]:
    candidates = [
        row for row in rows
        if row.get("split") in {"train", "validation"}
        and row.get("llm_decision") in {"KEEP", "DROP"}
    ]
    grouped: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in candidates:
        key = (
            str(row.get("split")),
            str(row.get("qtype")),
            str(row.get("llm_decision")),
            str(row.get("confidence")),
        )
        grouped[key].append(row)

    rng = random.Random(seed)
    groups = list(grouped.items())
    for _, group in groups:
        rng.shuffle(group)
    groups.sort(key=lambda item: (item[0][1] not in risk_qtypes, item[0]))

    selected: list[dict[str, Any]] = []
    cursor = 0
    while len(selected) < sample_size and groups:
        key, group = groups[cursor % len(groups)]
        if group:
            row = group.pop()
            selected.append(
                {
                    "vqa_id": row.get("vqa_id"),
                    "image_id": row.get("image_id"),
                    "split": row.get("split"),
                    "qtype": row.get("qtype"),
                    "llm_decision": row.get("llm_decision"),
                    "confidence": row.get("confidence"),
                    "stratum": "|".join(key),
                    "rationale_short": row.get("rationale_short", ""),
                }
            )
        groups = [(group_key, rows_left) for group_key, rows_left in groups if rows_left]
        cursor += 1
    return selected


def _priority(
    row: dict[str, Any],
    flags: list[str],
    risk_qtypes: set[str],
    *,
    mismatch: bool,
) -> str:
    if mismatch or any(flag in {"parse_failure", "missing_q0_score", "missing_q1_score"} for flag in flags):
        return "P0"
    if row.get("qtype") in risk_qtypes or any("triple" in flag for flag in flags):
        return "P1"
    return "P2"

