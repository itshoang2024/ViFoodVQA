from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_report(
    path: Path,
    *,
    run_id: str,
    command: str,
    cfg: dict[str, Any],
    split_summary: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    review_queue: list[dict[str, Any]],
    audit_sample: list[dict[str, Any]],
    metadata_summary: dict[str, Any] | None = None,
) -> None:
    model_cfg = cfg["model"]
    lines = [
        f"# LLM-Assisted Verification Report: `{run_id}`",
        "",
        "## Metadata",
        "",
        f"- Created at: `{datetime.now(timezone.utc).isoformat()}`",
        f"- Command: `{command}`",
        f"- Model: `{model_cfg.get('model_id')}`",
        f"- Prompt version: `{cfg['run']['prompt_version']}`",
        f"- Temperature: `{cfg['run']['temperature']}`",
        f"- Max output tokens: `{cfg['run']['max_output_tokens']}`",
        "",
        "## Source Splits",
        "",
        "| Split | Rows | Unique images | QTypes |",
        "| --- | ---: | ---: | --- |",
    ]
    for item in split_summary:
        qtypes = ", ".join(f"{key}:{value}" for key, value in sorted(item["qtypes"].items()))
        lines.append(
            f"| `{item['split']}` | {item['rows']} | {item['unique_images']} | {qtypes} |"
        )

    if metadata_summary:
        source_counts = ", ".join(
            f"{key}:{value}"
            for key, value in sorted((metadata_summary.get("effective_source_counts") or {}).items())
        )
        lines.extend(
            [
                "",
                "## Image Metadata",
                "",
                f"- Requested source: `{metadata_summary.get('requested_source')}`",
                f"- Effective source counts: `{source_counts or 'n/a'}`",
                f"- Rows missing metadata: `{metadata_summary.get('metadata_missing_count')}`",
                f"- Missing `food_items`: `{metadata_summary.get('missing_food_items_count')}`",
                f"- Missing `image_desc`: `{metadata_summary.get('missing_image_desc_count')}`",
                f"- Lookup failures: `{metadata_summary.get('lookup_failure_count')}`",
            ]
        )

    decisions = Counter(str(row.get("llm_decision")) for row in rows)
    lines.extend(
        [
            "",
            "## Decision Distribution",
            "",
            "| Decision | Rows |",
            "| --- | ---: |",
        ]
    )
    for decision in ["KEEP", "DROP", "REVIEW"]:
        lines.append(f"| `{decision}` | {decisions[decision]} |")

    lines.extend(
        [
            "",
            "## Review And Audit",
            "",
            f"- Review queue rows: `{len(review_queue)}`",
            f"- Audit sample rows: `{len(audit_sample)}`",
            "- Human review is still required for every `REVIEW` row.",
            "- Public claims must distinguish human-verified `test` from LLM-assisted `train` and `validation`.",
            "",
            "## Known Limitations",
            "",
            "- GPT answer accuracy is not equivalent to verification accuracy.",
            "- Local Hugging Face-style test exports may contain only human-kept rows, so false KEEP can be `n/a` unless dropped test rows are provided.",
            "- No Supabase field is updated by this workflow.",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
