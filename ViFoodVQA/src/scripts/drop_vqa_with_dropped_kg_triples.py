from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from collect_ground_truth_stats import (
    DEFAULT_SUPABASE_ENV,
    PAGE_SIZE,
    make_supabase_client,
    normalize_split,
    require_supabase_config,
)


BATCH_SIZE = 100
SAMPLE_LIMIT = 50
VERIFY_RULE = "KG_TRIPLE_DROP_CASCADE_V1"
VERIFY_NOTE = (
    "Auto-dropped because triples_used references kg_triple_catalog.is_drop=true "
    f"({VERIFY_RULE})."
)
VQA_SELECT_COLUMNS = (
    "vqa_id,image_id,qtype,split,question,choice_a,choice_b,choice_c,choice_d,"
    "answer,is_checked,is_drop,verify_decision,verify_rule,verify_notes,triples_used"
)


def configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8")
            except Exception:
                pass


@dataclass(frozen=True)
class CatalogIndex:
    by_id: dict[int, dict[str, Any]]
    by_key: dict[tuple[str, str, str], dict[str, Any]]


def norm_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().split())


def triple_key(item: dict[str, Any]) -> tuple[str, str, str] | None:
    subject = norm_text(item.get("subject"))
    relation = norm_text(item.get("relation"))
    target = norm_text(item.get("target"))
    if not subject or not relation or not target:
        return None
    return subject, relation, target


def parse_jsonish(value: Any) -> Any:
    if value is None:
        return []
    if isinstance(value, (list, dict)):
        return value
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return []
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return []
    return []


def parse_triples_used(value: Any) -> list[dict[str, Any]]:
    data = parse_jsonish(value)
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]


def fetch_vqa_rows(client: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        response = (
            client.table("vqa")
            .select(VQA_SELECT_COLUMNS)
            .order("vqa_id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = response.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return rows


def fetch_catalog_rows(client: Any) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0

    while True:
        response = (
            client.table("kg_triple_catalog")
            .select("triple_id,subject,relation,target,is_drop")
            .order("triple_id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )
        batch = response.data or []
        if not batch:
            break
        rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        start += PAGE_SIZE

    return rows


def build_catalog_index(catalog_rows: list[dict[str, Any]]) -> CatalogIndex:
    by_id: dict[int, dict[str, Any]] = {}
    by_key: dict[tuple[str, str, str], dict[str, Any]] = {}

    for row in catalog_rows:
        triple_id = row.get("triple_id")
        if triple_id is not None:
            by_id[int(triple_id)] = row

        key = triple_key(row)
        if key is not None:
            by_key[key] = row

    return CatalogIndex(by_id=by_id, by_key=by_key)


def find_catalog_row_for_triple(
    triple: dict[str, Any],
    catalog: CatalogIndex,
) -> tuple[dict[str, Any] | None, str]:
    triple_id = triple.get("triple_id")
    if triple_id is not None:
        try:
            catalog_row = catalog.by_id.get(int(triple_id))
        except (TypeError, ValueError):
            catalog_row = None
        if catalog_row is not None:
            return catalog_row, "triple_id"

    key = triple_key(triple)
    if key is None:
        return None, "invalid_triple"

    catalog_row = catalog.by_key.get(key)
    if catalog_row is not None:
        return catalog_row, "subject_relation_target"

    return None, "missing_catalog"


def inspect_vqa_row(
    row: dict[str, Any],
    catalog: CatalogIndex,
) -> dict[str, Any]:
    dropped_matches: list[dict[str, Any]] = []
    missing_triples: list[dict[str, Any]] = []
    invalid_triples: list[dict[str, Any]] = []
    match_methods: Counter[str] = Counter()

    for index, triple in enumerate(parse_triples_used(row.get("triples_used"))):
        catalog_row, method = find_catalog_row_for_triple(triple, catalog)
        match_methods[method] += 1

        if catalog_row is None:
            entry = {
                "index": index,
                "subject": norm_text(triple.get("subject")),
                "relation": norm_text(triple.get("relation")),
                "target": norm_text(triple.get("target")),
                "reason": method,
            }
            if method == "invalid_triple":
                invalid_triples.append(entry)
            else:
                missing_triples.append(entry)
            continue

        if catalog_row.get("is_drop") is True:
            dropped_matches.append(
                {
                    "index": index,
                    "triple_id": catalog_row.get("triple_id"),
                    "subject": norm_text(catalog_row.get("subject")),
                    "relation": norm_text(catalog_row.get("relation")),
                    "target": norm_text(catalog_row.get("target")),
                    "match_method": method,
                }
            )

    return {
        "vqa_id": row.get("vqa_id"),
        "image_id": row.get("image_id"),
        "qtype": row.get("qtype") or "<empty>",
        "split": normalize_split(row.get("split")),
        "question": row.get("question"),
        "choice_a": row.get("choice_a"),
        "choice_b": row.get("choice_b"),
        "choice_c": row.get("choice_c"),
        "choice_d": row.get("choice_d"),
        "answer": row.get("answer"),
        "is_checked": row.get("is_checked"),
        "is_drop": row.get("is_drop"),
        "verify_decision": row.get("verify_decision") or "<null>",
        "verify_rule": row.get("verify_rule"),
        "verify_notes": row.get("verify_notes"),
        "dropped_triples": dropped_matches,
        "missing_catalog_triples": missing_triples,
        "invalid_triples": invalid_triples,
        "match_methods": dict(match_methods),
    }


def analyze_rows(
    vqa_rows: list[dict[str, Any]],
    catalog_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    catalog = build_catalog_index(catalog_rows)
    inspected = [inspect_vqa_row(row, catalog) for row in vqa_rows]

    affected_rows = [
        row for row in inspected
        if row["is_drop"] is not True and row["dropped_triples"]
    ]
    already_dropped_affected_rows = [
        row for row in inspected
        if row["is_drop"] is True and row["dropped_triples"]
    ]
    rows_with_missing_catalog = [
        row for row in inspected
        if row["missing_catalog_triples"]
    ]
    rows_with_invalid_triples = [
        row for row in inspected
        if row["invalid_triples"]
    ]

    match_methods: Counter[str] = Counter()
    for row in inspected:
        match_methods.update(row["match_methods"])

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "verify_rule": VERIFY_RULE,
        "catalog_total": len(catalog_rows),
        "catalog_dropped": sum(1 for row in catalog_rows if row.get("is_drop") is True),
        "catalog_kept": sum(1 for row in catalog_rows if row.get("is_drop") is not True),
        "raw_vqa_total": len(vqa_rows),
        "active_vqa_total": sum(1 for row in vqa_rows if row.get("is_drop") is not True),
        "affected_count": len(affected_rows),
        "affected_split_counts": sorted_counter(Counter(row["split"] for row in affected_rows)),
        "affected_qtype_counts": sorted_counter(Counter(row["qtype"] for row in affected_rows)),
        "affected_is_checked_counts": sorted_counter(Counter(str(row["is_checked"]) for row in affected_rows)),
        "affected_verify_decision_counts": sorted_counter(Counter(row["verify_decision"] for row in affected_rows)),
        "affected_unique_image_ids": len({row["image_id"] for row in affected_rows if row["image_id"]}),
        "affected_vqa_ids": [row["vqa_id"] for row in affected_rows if row["vqa_id"] is not None],
        "affected_rows": affected_rows,
        "affected_test_count": sum(1 for row in affected_rows if row["split"] == "test"),
        "affected_test_vqa_ids": [
            row["vqa_id"]
            for row in affected_rows
            if row["split"] == "test" and row["vqa_id"] is not None
        ],
        "affected_test_rows": [
            row for row in affected_rows
            if row["split"] == "test"
        ],
        "affected_rows_sample": sample_rows(affected_rows, SAMPLE_LIMIT),
        "already_dropped_affected_count": len(already_dropped_affected_rows),
        "already_dropped_affected_split_counts": sorted_counter(
            Counter(row["split"] for row in already_dropped_affected_rows)
        ),
        "rows_with_missing_catalog_triples": len(rows_with_missing_catalog),
        "missing_catalog_split_counts": sorted_counter(Counter(row["split"] for row in rows_with_missing_catalog)),
        "missing_catalog_rows_sample": sample_rows(rows_with_missing_catalog, SAMPLE_LIMIT),
        "rows_with_invalid_triples": len(rows_with_invalid_triples),
        "invalid_triples_rows_sample": sample_rows(rows_with_invalid_triples, SAMPLE_LIMIT),
        "match_method_counts": sorted_counter(match_methods),
    }


def sorted_counter(counter: Counter[Any]) -> dict[str, int]:
    return {str(key): counter[key] for key in sorted(counter, key=str)}


def sample_rows(rows: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    output = []
    for row in rows[:limit]:
        output.append(
            {
                "vqa_id": row["vqa_id"],
                "image_id": row["image_id"],
                "split": row["split"],
                "qtype": row["qtype"],
                "question": row.get("question"),
                "answer": row.get("answer"),
                "is_checked": row["is_checked"],
                "verify_decision": row["verify_decision"],
                "dropped_triples": row["dropped_triples"],
                "missing_catalog_triples": row["missing_catalog_triples"],
                "invalid_triples": row["invalid_triples"],
            }
        )
    return output


def chunks(items: list[int], size: int) -> list[list[int]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def append_verify_note(existing: Any) -> str:
    existing_text = "" if existing is None else str(existing).strip()
    if not existing_text:
        return VERIFY_NOTE
    if VERIFY_RULE in existing_text:
        return existing_text
    return f"{existing_text}\n{VERIFY_NOTE}"


def apply_drop(client: Any, affected_rows: list[dict[str, Any]]) -> int:
    if not affected_rows:
        return 0

    updated_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    updated = 0
    for row in affected_rows:
        vqa_id = int(row["vqa_id"])
        response = (
            client.table("vqa")
            .update(
                {
                    "is_drop": True,
                    "verify_decision": "DROP",
                    "verify_rule": VERIFY_RULE,
                    "verify_notes": append_verify_note(row.get("verify_notes")),
                    "updated_at": updated_at,
                }
            )
            .eq("vqa_id", vqa_id)
            .eq("is_drop", False)
            .execute()
        )
        if response.data:
            updated += 1
        if updated % 25 == 0 or updated == len(affected_rows):
            print(f"Updated {updated}/{len(affected_rows)} rows...", flush=True)

    return updated


def artifact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "vqa_id": row.get("vqa_id"),
        "image_id": row.get("image_id"),
        "split": row.get("split"),
        "qtype": row.get("qtype"),
        "question": row.get("question"),
        "choice_a": row.get("choice_a"),
        "choice_b": row.get("choice_b"),
        "choice_c": row.get("choice_c"),
        "choice_d": row.get("choice_d"),
        "answer": row.get("answer"),
        "is_checked": row.get("is_checked"),
        "is_drop": row.get("is_drop"),
        "verify_decision": row.get("verify_decision"),
        "verify_rule": row.get("verify_rule"),
        "verify_notes": row.get("verify_notes"),
        "dropped_triples": row.get("dropped_triples", []),
        "missing_catalog_triples": row.get("missing_catalog_triples", []),
        "invalid_triples": row.get("invalid_triples", []),
        "match_methods": row.get("match_methods", {}),
    }


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "vqa_id",
        "image_id",
        "split",
        "qtype",
        "question",
        "choice_a",
        "choice_b",
        "choice_c",
        "choice_d",
        "answer",
        "is_checked",
        "is_drop",
        "verify_decision",
        "verify_rule",
        "verify_notes",
        "dropped_triples",
        "missing_catalog_triples",
        "invalid_triples",
        "match_methods",
    ]
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            serialized = row.copy()
            for key in ("dropped_triples", "missing_catalog_triples", "invalid_triples", "match_methods"):
                serialized[key] = json.dumps(serialized.get(key), ensure_ascii=False)
            writer.writerow(serialized)


def write_artifacts(summary: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    affected_rows = [artifact_row(row) for row in summary["affected_rows"]]
    affected_test_rows = [artifact_row(row) for row in summary["affected_test_rows"]]
    summary_for_file = {
        key: value
        for key, value in summary.items()
        if key not in {"affected_rows", "affected_test_rows"}
    }

    write_json(output_dir / "summary.json", summary_for_file)
    write_json(output_dir / "affected_vqa.json", affected_rows)
    write_json(output_dir / "affected_test_vqa.json", affected_test_rows)
    write_csv(output_dir / "affected_vqa.csv", affected_rows)
    write_csv(output_dir / "affected_test_vqa.csv", affected_test_rows)
    print(f"Wrote incident artifacts to {output_dir}", flush=True)


def print_summary(summary: dict[str, Any], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return

    print("Dropped-KG-triple VQA cleanup")
    print(f"Catalog triples: {summary['catalog_total']}")
    print(f"  kept     : {summary['catalog_kept']}")
    print(f"  is_drop  : {summary['catalog_dropped']}")
    print(f"Raw VQA rows: {summary['raw_vqa_total']}")
    print(f"Active VQA rows: {summary['active_vqa_total']}")
    print(f"Affected active VQA rows to drop: {summary['affected_count']}")
    print(f"Affected unique image IDs: {summary['affected_unique_image_ids']}")
    print(f"Affected split counts: {summary['affected_split_counts']}")
    print(f"Affected test VQA rows: {summary['affected_test_count']}")
    print(f"Affected test vqa_id values: {summary['affected_test_vqa_ids']}")
    print(f"Affected qtype counts: {summary['affected_qtype_counts']}")
    print(f"Affected is_checked counts: {summary['affected_is_checked_counts']}")
    print(f"Affected verify_decision counts: {summary['affected_verify_decision_counts']}")
    print(f"Already-dropped rows that also reference dropped KG triples: {summary['already_dropped_affected_count']}")
    print(f"Already-dropped affected split counts: {summary['already_dropped_affected_split_counts']}")
    print(f"Rows with triples_used not found in catalog: {summary['rows_with_missing_catalog_triples']}")
    print(f"Missing-catalog split counts: {summary['missing_catalog_split_counts']}")
    print(f"Rows with invalid triple objects in triples_used: {summary['rows_with_invalid_triples']}")
    print(f"Triple match method counts: {summary['match_method_counts']}")
    print(f"First 50 affected vqa_id values: {summary['affected_vqa_ids'][:50]}")
    print("First affected row samples:")
    for item in summary["affected_rows_sample"][:10]:
        print(json.dumps(item, ensure_ascii=False))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Mark Supabase VQA rows as dropped when triples_used references "
            "kg_triple_catalog rows with is_drop=true."
        )
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply updates. Default is dry-run only.",
    )
    parser.add_argument(
        "--env",
        type=Path,
        default=DEFAULT_SUPABASE_ENV,
        help=f"Supabase .env path. Default: {DEFAULT_SUPABASE_ENV}",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=BATCH_SIZE,
        help="Deprecated; retained for CLI compatibility.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="Write incident artifacts into this directory.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print summary as JSON.",
    )
    return parser.parse_args()


def main() -> int:
    configure_utf8_output()
    args = parse_args()
    config = require_supabase_config(args.env)
    client = make_supabase_client(config)

    catalog_rows = fetch_catalog_rows(client)
    vqa_rows = fetch_vqa_rows(client)
    summary = analyze_rows(vqa_rows, catalog_rows)
    summary["mode"] = "apply" if args.apply else "dry-run"

    print_summary(summary, as_json=args.json)
    if args.output_dir:
        write_artifacts(summary, args.output_dir)

    if not args.apply:
        if not args.json:
            print("Dry-run only. Pass --apply to set is_drop=true for affected VQA rows.")
        return 0

    updated = apply_drop(client, summary["affected_rows"])
    print(f"Applied cleanup. Updated rows: {updated}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
