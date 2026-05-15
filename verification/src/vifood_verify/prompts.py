from __future__ import annotations

import json
from typing import Any

from .data import VQARow


SYSTEM_PROMPT = """You are a strict ViFoodVQA dataset verifier.
You must apply the existing Q0/Q1/Q2 verification rubric:
- Q0: Triple Used Validity
- Q1: Question Validity
- Q2: Choice Quality

Return exactly one valid JSON object. Do not include Markdown, prose outside
JSON, or comments. Be conservative: if evidence is ambiguous, choose REVIEW.
Do not treat answer accuracy alone as proof of verification quality."""


def build_pass1_messages(sample: VQARow) -> list[dict[str, Any]]:
    text = f"""Pass 1: verify the VQA row, not the triples.

Check:
- the question matches the image, image description, food items, and qtype;
- the gold answer is correct;
- the four choices are same-type, non-ambiguous, and do not contain multiple correct answers.

Return this JSON schema:
{{
  "q1_score": 1|2|3|4,
  "q2_score": 1|2|3|4,
  "answer_valid": true|false,
  "choices_valid": true|false,
  "pass_decision": "KEEP"|"DROP"|"REVIEW",
  "confidence": "high"|"medium"|"low",
  "failure_flags": ["short_flag"],
  "rationale_short": "one concise Vietnamese or English explanation"
}}

VQA row:
{_sample_json(sample, include_triples=False)}
"""
    return _messages(sample, text)


def build_pass2_messages(sample: VQARow) -> list[dict[str, Any]]:
    text = f"""Pass 2: verify only triples_used in the context of this image and VQA.

For each triple, decide whether it is:
- valid: factually correct, relevant to the current image/VQA, and useful as support;
- invalid: wrong, irrelevant, hallucinated, or unsuitable for this VQA;
- needs_edit: direction is right but a field needs correction;
- unsure: insufficient evidence.

Return this JSON schema:
{{
  "q0_score": 1|2|3|4,
  "triple_reviews": [
    {{
      "index": 0,
      "status": "valid"|"invalid"|"needs_edit"|"unsure",
      "issue": "short issue or empty string"
    }}
  ],
  "pass_decision": "KEEP"|"DROP"|"REVIEW",
  "confidence": "high"|"medium"|"low",
  "failure_flags": ["short_flag"],
  "rationale_short": "one concise Vietnamese or English explanation"
}}

VQA row:
{_sample_json(sample, include_triples=True)}
"""
    return _messages(sample, text)


def build_pass3_messages(sample: VQARow, pass1: dict[str, Any], pass2: dict[str, Any]) -> list[dict[str, Any]]:
    text = f"""Pass 3: adversarial consistency review.

You are given the row plus the previous two verifier outputs. Try to find
strong reasons this row should not be silently accepted.

Reject or route to REVIEW if you find:
- multiple plausible correct choices;
- the question can be answered while triples_used are wrong or irrelevant;
- visual evidence is too ambiguous;
- triples_used contain unsupported food facts;
- Pass 1 and Pass 2 disagree.

Return this JSON schema:
{{
  "risk_level": "low"|"medium"|"high",
  "adversarial_findings": ["short finding"],
  "pass_decision": "KEEP"|"DROP"|"REVIEW",
  "confidence": "high"|"medium"|"low",
  "failure_flags": ["short_flag"],
  "rationale_short": "one concise Vietnamese or English explanation"
}}

Previous verifier outputs:
{json.dumps({"pass1": pass1, "pass2": pass2}, ensure_ascii=False, indent=2)}

VQA row:
{_sample_json(sample, include_triples=True)}
"""
    return _messages(sample, text)


def _messages(sample: VQARow, text: str) -> list[dict[str, Any]]:
    return [
        {
            "role": "system",
            "content": [{"type": "text", "text": SYSTEM_PROMPT}],
        },
        {
            "role": "user",
            "content": [
                {"type": "image", "path": sample.image_path},
                {"type": "text", "text": text},
            ],
        },
    ]


def _sample_json(sample: VQARow, *, include_triples: bool) -> str:
    payload = {
        "vqa_id": sample.vqa_id,
        "image_id": sample.image_id,
        "split": sample.split,
        "qtype": sample.qtype,
        "food_items": sample.row.get("food_items", []),
        "image_desc": sample.row.get("image_desc") or sample.row.get("image_description") or "",
        "question": sample.row["question"],
        "choices": sample.choices,
        "answer": sample.row["answer"],
    }
    if include_triples:
        payload["triples_used"] = sample.triples_used
    return json.dumps(payload, ensure_ascii=False, indent=2)

