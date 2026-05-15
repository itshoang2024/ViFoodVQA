from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from vifood_verify.run import main


def temp_dir() -> TemporaryDirectory[str]:
    root = Path(os.environ.get("VIFOOD_VERIFY_TEST_TMP", "C:/tmp"))
    root.mkdir(parents=True, exist_ok=True)
    return TemporaryDirectory(dir=root)


class RunSmokeTests(unittest.TestCase):
    def test_calibrate_dry_run_writes_expected_artifacts(self) -> None:
        with temp_dir() as tmp:
            root = Path(tmp)
            data_dir = root / "dataset"
            config_dir = root / "verification" / "configs"
            output_dir = root / "verification" / "outputs"
            (data_dir / "data").mkdir(parents=True)
            (data_dir / "images").mkdir()
            (config_dir).mkdir(parents=True)
            (data_dir / "images" / "image1.png").write_bytes(b"not-real-image")
            row = {
                "vqa_id": 1,
                "image_id": "image1",
                "image": "images/image1.png",
                "qtype": "ingredients",
                "question": "Món này có nguyên liệu nào?",
                "choices": {"A": "Thịt bò", "B": "Huế", "C": "Chiên", "D": "Ngọt"},
                "answer": "A",
                "triples_used": [{"subject": "Phở bò", "relation": "hasIngredient", "target": "Thịt bò"}],
            }
            (data_dir / "data" / "test.jsonl").write_text(
                json.dumps(row, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            config_path = config_dir / "verify.yaml"
            config_path.write_text(
                "\n".join(
                    [
                        "dataset:",
                        f"  data_dir: {data_dir.as_posix()}",
                        "  calibration_split: test",
                        "  target_splits: [train, validation]",
                        "paths:",
                        f"  output_dir: {output_dir.as_posix()}",
                    ]
                ),
                encoding="utf-8",
            )

            argv = [
                "vifood_verify",
                "calibrate",
                "--config",
                str(config_path),
                "--run-id",
                "smoke",
                "--dry-run",
                "--no-progress",
            ]
            with patch.object(sys, "argv", argv):
                main()

            run_dir = output_dir / "smoke"
            self.assertTrue((run_dir / "calibration_test.jsonl").exists())
            self.assertTrue((run_dir / "metrics_overall.csv").exists())
            self.assertTrue((run_dir / "review_queue.csv").exists())
            self.assertTrue((run_dir / "report.md").exists())


if __name__ == "__main__":
    unittest.main()

