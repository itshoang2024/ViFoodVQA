from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_eval.prune_predictions import find_prediction_files, prune_prediction_files
from vifood_eval.report import _prediction_files


def temp_dir() -> TemporaryDirectory[str]:
    root = Path(os.environ.get("VIFOOD_EVAL_TEST_TMP", "C:/tmp"))
    root.mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(dir=root)


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_report_loads_root_level_prediction_files_when_no_predictions_dir():
    with temp_dir() as tmp:
        run_dir = Path(tmp) / "qwen_bm25"
        write_jsonl(run_dir / "qwen3_vl_2b__bm25.jsonl", [{"vqa_id": 1}])
        write_jsonl(run_dir / "qwen3_vl_2b.jsonl", [{"vqa_id": 1}])

        files = _prediction_files(run_dir)

        assert [path.name for path in files] == ["qwen3_vl_2b__bm25.jsonl"]


def test_report_prefers_predictions_dir_layout():
    with temp_dir() as tmp:
        run_dir = Path(tmp) / "gpt"
        write_jsonl(run_dir / "predictions" / "gpt__bm25.jsonl", [{"vqa_id": 1}])
        write_jsonl(run_dir / "gpt__stale.jsonl", [{"vqa_id": 2}])

        files = _prediction_files(run_dir)

        assert [path.name for path in files] == ["gpt__bm25.jsonl"]


def test_prune_predictions_backs_up_and_skips_non_prediction_jsonl():
    with temp_dir() as tmp:
        outputs_dir = Path(tmp) / "outputs"
        prediction = outputs_dir / "qwen_bm25" / "qwen3_vl_2b__bm25.jsonl"
        classifier = outputs_dir / "qwen_bm25" / "qwen3_vl_2b.jsonl"
        backup = outputs_dir / "_prune_backups" / "old" / "qwen_bm25" / "qwen3_vl_2b__bm25.jsonl"
        write_jsonl(prediction, [{"vqa_id": 1}, {"vqa_id": 2}, {"vqa_id": 3}])
        write_jsonl(classifier, [{"vqa_id": 1}])
        write_jsonl(backup, [{"vqa_id": 1}])

        files = find_prediction_files(outputs_dir)
        report = prune_prediction_files(
            prediction_files=files,
            affected_ids={2, 99},
            outputs_dir=outputs_dir,
            run_id="test",
            apply=True,
        )

        assert files == [prediction]
        assert report["total_removed_rows"] == 1
        assert report["files"][0]["affected_ids_absent"] == [99]
        assert (outputs_dir / "_prune_backups" / "test" / "qwen_bm25" / "qwen3_vl_2b__bm25.jsonl").exists()
        rows = [json.loads(line) for line in prediction.read_text(encoding="utf-8").splitlines()]
        assert [row["vqa_id"] for row in rows] == [1, 3]
