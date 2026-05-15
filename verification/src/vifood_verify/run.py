from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from tqdm import tqdm

from .audit import build_audit_sample, build_review_queue
from .config import load_config, resolve_verification_path
from .data import (
    VQARow,
    infer_human_decision,
    load_splits,
    read_jsonl,
    split_summary,
    write_jsonl_row,
)
from .metrics import compute_metrics, write_csv
from .metadata import enrich_rows_by_split
from .model import make_model
from .report import write_report
from .verifier import verify_sample


def main() -> None:
    parser = argparse.ArgumentParser(description="Run ViFoodVQA LLM-assisted verification.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ["calibrate", "verify", "all"]:
        sub = subparsers.add_parser(name)
        _add_common_args(sub)
    args = parser.parse_args()

    cfg = load_config(args.config)
    command = str(args.command)
    if args.dry_run:
        cfg["model"] = {"type": "dry_run", "model_id": "dry_run"}

    run_id = args.run_id or datetime.now().strftime("%Y%m%d_%H%M%S")
    output_root = resolve_verification_path(cfg, cfg["paths"]["output_dir"])
    run_dir = output_root / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "config.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    calibration_split = cfg["dataset"]["calibration_split"]
    target_splits = list(cfg["dataset"]["target_splits"])
    if args.splits:
        target_splits = args.splits

    if command == "calibrate":
        splits = [calibration_split]
    elif command == "verify":
        _require_calibration_gate(args)
        splits = target_splits
    else:
        splits = [calibration_split, *target_splits]

    data_dir = resolve_verification_path(cfg, cfg["dataset"]["data_dir"])
    rows_by_split = load_splits(
        data_dir,
        splits,
        require_nonempty_triples=bool(cfg["dataset"].get("require_nonempty_triples", True)),
    )
    rows_by_split = _select_rows_by_split(
        rows_by_split,
        sample_ids=args.sample_ids,
        limit=args.limit,
        row_start=args.row_start,
        row_end=args.row_end,
    )
    metadata_summary = enrich_rows_by_split(rows_by_split, cfg.get("metadata", {}))
    (run_dir / "metadata_summary.json").write_text(
        json.dumps(metadata_summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    summary = split_summary(rows_by_split)
    (run_dir / "split_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    model = make_model(cfg["model"])
    for split, rows in rows_by_split.items():
        _run_split(
            cfg=cfg,
            run_id=run_id,
            run_dir=run_dir,
            split=split,
            rows=rows,
            model=model,
            resume=args.resume,
            progress=not args.no_progress,
        )

    all_rows = _load_run_rows(run_dir)
    _write_outputs(
        cfg=cfg,
        command=command,
        run_id=run_id,
        run_dir=run_dir,
        split_summary_rows=summary,
        rows=all_rows,
    )


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--config", default="configs/verify_gpt55.yaml")
    parser.add_argument("--run-id")
    parser.add_argument("--splits", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--row-start", type=int, help="1-based inclusive global row start after split loading.")
    parser.add_argument("--row-end", type=int, help="1-based inclusive global row end after split loading.")
    parser.add_argument("--sample-ids", nargs="*", type=int)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-progress", action="store_true")
    parser.add_argument("--calibration-run-dir")
    parser.add_argument("--skip-calibration-gate", action="store_true")


def _require_calibration_gate(args: argparse.Namespace) -> None:
    if args.skip_calibration_gate:
        return
    if not args.calibration_run_dir:
        raise SystemExit(
            "`verify` requires --calibration-run-dir unless --skip-calibration-gate is set."
        )
    run_dir = Path(args.calibration_run_dir)
    if not run_dir.exists():
        raise SystemExit(f"Calibration run directory does not exist: {run_dir}")
    if not (run_dir / "metrics_overall.csv").exists():
        raise SystemExit(f"Missing calibration metrics: {run_dir / 'metrics_overall.csv'}")


def _run_split(
    *,
    cfg: dict[str, Any],
    run_id: str,
    run_dir: Path,
    split: str,
    rows: list[VQARow],
    model: Any,
    resume: bool,
    progress: bool,
) -> None:
    out_path = _split_output_path(run_dir, split, cfg["dataset"]["calibration_split"])
    completed = _completed_ids(out_path) if resume else set()
    bar = tqdm(
        rows,
        desc=f"verify/{split}",
        unit="row",
        disable=not progress,
    )
    for sample in bar:
        if sample.vqa_id in completed:
            continue
        bar.set_postfix({"vqa_id": sample.vqa_id, "out": out_path.name})
        result = verify_sample(
            sample,
            model=model,
            model_id=str(cfg["model"].get("model_id", cfg["model"].get("name", "unknown"))),
            run_id=run_id,
            prompt_version=str(cfg["run"]["prompt_version"]),
            max_output_tokens=int(cfg["run"]["max_output_tokens"]),
            temperature=float(cfg["run"]["temperature"]),
        )
        result["human_decision"] = infer_human_decision(
            sample,
            assume_test_keep=bool(cfg["dataset"].get("assume_test_rows_are_human_keep", True)),
        )
        if "_global_row_index" in sample.row:
            result["global_row_index"] = sample.row["_global_row_index"]
        result["metadata_source"] = sample.row.get("_metadata_source", "missing")
        result["metadata_missing_fields"] = sample.row.get("_metadata_missing_fields", [])
        write_jsonl_row(out_path, result)


def _write_outputs(
    *,
    cfg: dict[str, Any],
    command: str,
    run_id: str,
    run_dir: Path,
    split_summary_rows: list[dict[str, Any]],
    rows: list[dict[str, Any]],
) -> None:
    overall, by_qtype = compute_metrics(rows)
    write_csv(run_dir / "metrics_overall.csv", overall, ["scope", "metric", "value"])
    write_csv(
        run_dir / "metrics_by_qtype.csv",
        by_qtype,
        [
            "split",
            "qtype",
            "total",
            "llm_keep",
            "llm_drop",
            "llm_review",
            "review_rate",
            "human_keep",
            "human_drop",
            "agreement_rate",
            "false_keep_rate",
            "false_drop_rate",
        ],
    )

    risk_qtypes = set(cfg["run"].get("risk_qtypes", []))
    review_queue = build_review_queue(rows, risk_qtypes=risk_qtypes)
    audit_sample = build_audit_sample(
        rows,
        sample_size=int(cfg["audit"]["sample_size"]),
        seed=int(cfg["run"]["seed"]),
        risk_qtypes=risk_qtypes,
    )
    write_csv(
        run_dir / "review_queue.csv",
        review_queue,
        [
            "priority",
            "reason",
            "vqa_id",
            "image_id",
            "split",
            "qtype",
            "llm_decision",
            "human_decision",
            "confidence",
            "failure_flags",
            "rationale_short",
        ],
    )
    write_csv(
        run_dir / "audit_sample.csv",
        audit_sample,
        [
            "vqa_id",
            "image_id",
            "split",
            "qtype",
            "llm_decision",
            "confidence",
            "stratum",
            "rationale_short",
        ],
    )
    write_report(
        run_dir / "report.md",
        run_id=run_id,
        command=command,
        cfg=cfg,
        split_summary=split_summary_rows,
        rows=rows,
        review_queue=review_queue,
        audit_sample=audit_sample,
        metadata_summary=_read_metadata_summary(run_dir),
    )


def _select_rows_by_split(
    rows_by_split: dict[str, list[VQARow]],
    *,
    sample_ids: list[int] | None,
    limit: int | None,
    row_start: int | None,
    row_end: int | None,
) -> dict[str, list[VQARow]]:
    if row_start is not None or row_end is not None:
        if sample_ids:
            raise ValueError("--row-start/--row-end cannot be combined with --sample-ids")
        if limit is not None:
            raise ValueError("--row-start/--row-end cannot be combined with --limit")
        return _select_global_row_range(rows_by_split, row_start=row_start, row_end=row_end)

    return {
        split: _select_rows(rows, sample_ids=sample_ids, limit=limit)
        for split, rows in rows_by_split.items()
    }


def _select_global_row_range(
    rows_by_split: dict[str, list[VQARow]],
    *,
    row_start: int | None,
    row_end: int | None,
) -> dict[str, list[VQARow]]:
    start = row_start or 1
    end = row_end
    total = sum(len(rows) for rows in rows_by_split.values())
    if start < 1:
        raise ValueError("--row-start must be >= 1")
    if end is not None and end < start:
        raise ValueError("--row-end must be >= --row-start")
    if start > total:
        raise ValueError(f"--row-start {start} exceeds loaded row count {total}")

    selected: dict[str, list[VQARow]] = {split: [] for split in rows_by_split}
    ordinal = 0
    for split, rows in rows_by_split.items():
        for row in rows:
            ordinal += 1
            if ordinal < start:
                continue
            if end is not None and ordinal > end:
                continue
            row.row["_global_row_index"] = ordinal
            selected[split].append(row)

    return selected


def _select_rows(rows: list[VQARow], *, sample_ids: list[int] | None, limit: int | None) -> list[VQARow]:
    selected = rows
    if sample_ids:
        wanted = set(sample_ids)
        selected = [row for row in selected if row.vqa_id in wanted]
        missing = sorted(wanted - {row.vqa_id for row in selected})
        if missing:
            raise KeyError(f"Requested VQA id(s) not found: {missing}")
    if limit:
        selected = selected[:limit]
    return selected


def _split_output_path(run_dir: Path, split: str, calibration_split: str) -> Path:
    if split == calibration_split:
        return run_dir / f"calibration_{split}.jsonl"
    return run_dir / f"{split}.jsonl"


def _load_run_rows(run_dir: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(run_dir.glob("*.jsonl")):
        rows.extend(read_jsonl(path))
    return rows


def _completed_ids(path: Path) -> set[int]:
    if not path.exists():
        return set()
    return {int(row["vqa_id"]) for row in read_jsonl(path)}


def _read_metadata_summary(run_dir: Path) -> dict[str, Any] | None:
    path = run_dir / "metadata_summary.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    main()
