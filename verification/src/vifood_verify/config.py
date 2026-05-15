from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


def load_config(path: str | Path) -> dict[str, Any]:
    config_path = Path(path).resolve()
    with config_path.open("r", encoding="utf-8") as f:
        loaded = yaml.safe_load(f) or {}

    cfg = _deep_merge(_defaults(), loaded)
    cfg["_config_path"] = str(config_path)
    cfg["_verification_root"] = str(config_path.parent.parent)
    cfg["_project_root"] = str(config_path.parent.parent.parent)

    verification_root = Path(cfg["_verification_root"])
    project_root = Path(cfg["_project_root"])
    load_dotenv(verification_root / ".env")
    load_dotenv(project_root / "ViFoodVQA" / ".env")
    load_dotenv(project_root / "evaluation" / ".env")
    return cfg


def verification_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["_verification_root"]).resolve()


def project_root(cfg: dict[str, Any]) -> Path:
    return Path(cfg["_project_root"]).resolve()


def resolve_verification_path(cfg: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return verification_root(cfg) / path


def resolve_project_path(cfg: dict[str, Any], value: str | Path) -> Path:
    path = Path(value)
    if path.is_absolute():
        return path
    return project_root(cfg) / path


def _defaults() -> dict[str, Any]:
    return {
        "dataset": {
            "data_dir": "../evaluation/data/vifoodvqa",
            "calibration_split": "test",
            "target_splits": ["train", "validation"],
            "require_nonempty_triples": True,
            "assume_test_rows_are_human_keep": True,
        },
        "metadata": {
            "source": "jsonl_embedded",
            "required": False,
            "table": "image",
            "columns": "image_id,food_items,image_desc",
            "batch_size": 200,
            "url_env": "SUPABASE_URL",
            "key_env": "SUPABASE_KEY",
        },
        "paths": {
            "output_dir": "outputs",
        },
        "run": {
            "seed": 42,
            "max_output_tokens": 1800,
            "temperature": 0,
            "prompt_version": "vqa_verify_gpt55_v1",
            "risk_qtypes": [
                "allergen_restrictions",
                "dietary_restrictions",
                "origin_locality",
                "substitution_rules",
            ],
        },
        "audit": {
            "sample_size": 120,
        },
        "model": {
            "type": "openai_compatible",
            "name": "gpt_5_5",
            "model_id": "gpt-5.5",
            "api_key_env": "OPENAI_COMPAT_API_KEY",
            "base_url_env": "OPENAI_COMPAT_BASE_URL",
            "json_response_format": True,
            "json_response_format_fallback": True,
        },
    }


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
