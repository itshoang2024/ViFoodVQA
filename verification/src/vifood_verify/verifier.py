from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from .data import VQARow
from .model import VerifierModel
from .parsing import (
    norm_confidence,
    norm_decision,
    norm_flags,
    norm_score,
    norm_triple_reviews,
    parse_json_object,
)
from .prompts import build_pass1_messages, build_pass2_messages, build_pass3_messages


CONFIDENCE_ORDER = {"low": 0, "medium": 1, "high": 2}


def verify_sample(
    sample: VQARow,
    *,
    model: VerifierModel,
    model_id: str,
    run_id: str,
    prompt_version: str,
    max_output_tokens: int,
    temperature: float,
) -> dict[str, Any]:
    pass1_raw, pass1, pass1_status, pass1_latency = _call_pass(
        model,
        build_pass1_messages(sample),
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    pass2_raw, pass2, pass2_status, pass2_latency = _call_pass(
        model,
        build_pass2_messages(sample),
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    pass3_raw, pass3, pass3_status, pass3_latency = _call_pass(
        model,
        build_pass3_messages(sample, pass1, pass2),
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    aggregate = aggregate_passes(
        pass1,
        pass2,
        pass3,
        parse_statuses=[pass1_status, pass2_status, pass3_status],
        expected_triples=len(sample.triples_used),
    )

    return {
        "vqa_id": sample.vqa_id,
        "image_id": sample.image_id,
        "split": sample.split,
        "qtype": sample.qtype,
        "q0_score": aggregate["q0_score"],
        "q1_score": aggregate["q1_score"],
        "q2_score": aggregate["q2_score"],
        "llm_decision": aggregate["llm_decision"],
        "triple_reviews": aggregate["triple_reviews"],
        "confidence": aggregate["confidence"],
        "failure_flags": aggregate["failure_flags"],
        "rationale_short": aggregate["rationale_short"],
        "model": model_id,
        "prompt_version": prompt_version,
        "run_id": run_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "pass_outputs": {
            "pass1": pass1,
            "pass2": pass2,
            "pass3": pass3,
        },
        "parse_statuses": {
            "pass1": pass1_status,
            "pass2": pass2_status,
            "pass3": pass3_status,
        },
        "raw_responses": {
            "pass1": pass1_raw,
            "pass2": pass2_raw,
            "pass3": pass3_raw,
        },
        "latency_s": {
            "pass1": round(pass1_latency, 4),
            "pass2": round(pass2_latency, 4),
            "pass3": round(pass3_latency, 4),
            "total": round(pass1_latency + pass2_latency + pass3_latency, 4),
        },
    }


def aggregate_passes(
    pass1: dict[str, Any],
    pass2: dict[str, Any],
    pass3: dict[str, Any],
    *,
    parse_statuses: list[str],
    expected_triples: int,
) -> dict[str, Any]:
    q1 = norm_score(pass1.get("q1_score"))
    q2 = norm_score(pass1.get("q2_score"))
    q0 = norm_score(pass2.get("q0_score"))
    triple_reviews = norm_triple_reviews(pass2.get("triple_reviews"))
    flags = _collect_flags(pass1, pass2, pass3)

    if any(status not in {"ok", "ok_extracted"} for status in parse_statuses):
        flags.append("parse_failure")
    for name, score in [("q0", q0), ("q1", q1), ("q2", q2)]:
        if score is None:
            flags.append(f"missing_{name}_score")
    if expected_triples and len(triple_reviews) != expected_triples:
        flags.append("triple_review_count_mismatch")

    pass_decisions = [
        norm_decision(pass1.get("pass_decision")),
        norm_decision(pass2.get("pass_decision")),
        norm_decision(pass3.get("pass_decision")),
    ]
    if any(decision is None for decision in pass_decisions):
        flags.append("missing_pass_decision")

    statuses = {review["status"] for review in triple_reviews}
    has_schema_failure = any(
        flag.startswith("missing_")
        or flag in {"parse_failure", "triple_review_count_mismatch"}
        for flag in flags
    )

    if has_schema_failure:
        decision = "REVIEW"
    elif q0 is not None and q0 <= 2:
        decision = "DROP"
    elif q1 is not None and q1 <= 2:
        decision = "DROP"
    elif q2 is not None and q2 <= 2:
        decision = "DROP"
    elif "needs_edit" in statuses or "unsure" in statuses:
        decision = "REVIEW"
    elif "invalid" in statuses:
        decision = "REVIEW"
        flags.append("invalid_triple_with_non_drop_score")
    elif "DROP" in pass_decisions:
        decision = "DROP"
    elif "REVIEW" in pass_decisions:
        decision = "REVIEW"
    elif pass_decisions == ["KEEP", "KEEP", "KEEP"]:
        decision = "KEEP"
    else:
        decision = "REVIEW"
        flags.append("pass_disagreement")

    confidences = [
        norm_confidence(pass1.get("confidence")),
        norm_confidence(pass2.get("confidence")),
        norm_confidence(pass3.get("confidence")),
    ]
    confidence = min(confidences, key=lambda item: CONFIDENCE_ORDER[item])
    if flags:
        confidence = "low" if decision == "REVIEW" else confidence

    return {
        "q0_score": q0,
        "q1_score": q1,
        "q2_score": q2,
        "llm_decision": decision,
        "triple_reviews": triple_reviews,
        "confidence": confidence,
        "failure_flags": sorted(set(flags)),
        "rationale_short": _combine_rationales(pass1, pass2, pass3),
    }


def _call_pass(
    model: VerifierModel,
    messages: list[dict[str, Any]],
    *,
    max_output_tokens: int,
    temperature: float,
) -> tuple[str, dict[str, Any], str, float]:
    started = time.perf_counter()
    raw = model.generate_json(
        messages,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
    )
    latency = time.perf_counter() - started
    parsed, status = parse_json_object(raw)
    return raw, parsed, status, latency


def _collect_flags(*passes: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    for payload in passes:
        flags.extend(norm_flags(payload.get("failure_flags")))
    return flags


def _combine_rationales(*passes: dict[str, Any]) -> str:
    parts = []
    for idx, payload in enumerate(passes, start=1):
        text = " ".join(str(payload.get("rationale_short") or "").split())
        if text:
            parts.append(f"P{idx}: {text}")
    return " | ".join(parts)
