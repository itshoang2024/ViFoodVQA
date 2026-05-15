from __future__ import annotations

import base64
from io import BytesIO
import mimetypes
import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class VerifierModel(ABC):
    @abstractmethod
    def generate_json(
        self,
        messages: list[dict[str, Any]],
        *,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        raise NotImplementedError


def make_model(cfg: dict[str, Any]) -> VerifierModel:
    model_type = cfg.get("type")
    if model_type == "openai_compatible":
        return OpenAICompatibleVerifierModel(cfg)
    if model_type == "dry_run":
        return DryRunVerifierModel()
    raise ValueError(f"Unsupported verifier model type: {model_type}")


class OpenAICompatibleVerifierModel(VerifierModel):
    def __init__(self, cfg: dict[str, Any]) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("Install the verification package with OpenAI support.") from exc

        api_key = os.getenv(cfg.get("api_key_env", "OPENAI_COMPAT_API_KEY"))
        base_url = os.getenv(cfg.get("base_url_env", "OPENAI_COMPAT_BASE_URL")) or None
        if not api_key:
            raise RuntimeError("Missing OpenAI-compatible API key environment variable.")

        self.model_id = cfg["model_id"]
        client_kwargs: dict[str, Any] = {"api_key": api_key, "base_url": base_url}
        if cfg.get("default_headers"):
            client_kwargs["default_headers"] = cfg["default_headers"]
        self.client = OpenAI(**client_kwargs)
        self.use_response_format = bool(cfg.get("json_response_format", True))
        self.response_format_fallback = bool(cfg.get("json_response_format_fallback", True))
        self.image_max_side = int(cfg.get("image_max_side", 1600))
        self.image_max_bytes = int(cfg.get("image_max_bytes", 2_000_000))
        self.image_jpeg_quality = int(cfg.get("image_jpeg_quality", 85))

    def generate_json(
        self,
        messages: list[dict[str, Any]],
        *,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        request: dict[str, Any] = {
            "model": self.model_id,
            "messages": _messages_to_openai(
                messages,
                image_max_side=self.image_max_side,
                image_max_bytes=self.image_max_bytes,
                image_jpeg_quality=self.image_jpeg_quality,
            ),
            "temperature": temperature,
            "max_tokens": max_output_tokens,
        }
        if self.use_response_format:
            request["response_format"] = {"type": "json_object"}

        try:
            response = self.client.chat.completions.create(**request)
        except Exception as exc:
            if (
                "response_format" not in request
                or not self.response_format_fallback
                or not _looks_like_response_format_error(exc)
            ):
                raise
            request.pop("response_format", None)
            response = self.client.chat.completions.create(**request)
        return response.choices[0].message.content or ""


class DryRunVerifierModel(VerifierModel):
    def generate_json(
        self,
        messages: list[dict[str, Any]],
        *,
        max_output_tokens: int,
        temperature: float,
    ) -> str:
        _ = (messages, max_output_tokens, temperature)
        return (
            '{"q0_score":3,"q1_score":3,"q2_score":3,'
            '"pass_decision":"REVIEW","confidence":"low",'
            '"triple_reviews":[],"failure_flags":["dry_run"],'
            '"rationale_short":"Dry run placeholder; no GPT call was made."}'
        )


def _messages_to_openai(
    messages: list[dict[str, Any]],
    *,
    image_max_side: int = 1600,
    image_max_bytes: int = 2_000_000,
    image_jpeg_quality: int = 85,
) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    for message in messages:
        parts: list[dict[str, Any]] = []
        for part in message["content"]:
            if part["type"] == "text":
                parts.append({"type": "text", "text": part["text"]})
            elif part["type"] == "image":
                parts.append(
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": _image_to_data_url(
                                Path(part["path"]),
                                max_side=image_max_side,
                                max_bytes=image_max_bytes,
                                jpeg_quality=image_jpeg_quality,
                            )
                        },
                    }
                )
        converted.append({"role": message["role"], "content": parts})
    return converted


def _image_to_data_url(
    path: Path,
    *,
    max_side: int = 1600,
    max_bytes: int = 2_000_000,
    jpeg_quality: int = 85,
) -> str:
    raw = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "image/jpeg"
    if len(raw) <= max_bytes and _image_fits_size(path, max_side=max_side):
        encoded = base64.b64encode(raw).decode("ascii")
        return f"data:{mime};base64,{encoded}"

    try:
        encoded_bytes = _compressed_image_bytes(
            path,
            max_side=max_side,
            max_bytes=max_bytes,
            jpeg_quality=jpeg_quality,
        )
        mime = "image/jpeg"
    except Exception:
        encoded_bytes = raw

    encoded = base64.b64encode(encoded_bytes).decode("ascii")
    return f"data:{mime};base64,{encoded}"


def _image_fits_size(path: Path, *, max_side: int) -> bool:
    try:
        from PIL import Image

        with Image.open(path) as image:
            return image.width <= max_side and image.height <= max_side
    except Exception:
        return True


def _compressed_image_bytes(
    path: Path,
    *,
    max_side: int,
    max_bytes: int,
    jpeg_quality: int,
) -> bytes:
    from PIL import Image, ImageOps

    with Image.open(path) as image:
        image = ImageOps.exif_transpose(image)
        image.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        if image.mode in {"RGBA", "LA"} or (
            image.mode == "P" and "transparency" in image.info
        ):
            background = Image.new("RGB", image.size, (255, 255, 255))
            background.paste(image, mask=image.convert("RGBA").split()[-1])
            image = background
        elif image.mode != "RGB":
            image = image.convert("RGB")

        qualities = [jpeg_quality, 80, 75, 70, 65]
        for quality in qualities:
            buffer = BytesIO()
            image.save(buffer, format="JPEG", quality=quality, optimize=True)
            payload = buffer.getvalue()
            if len(payload) <= max_bytes or quality == qualities[-1]:
                return payload


def _looks_like_response_format_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "response_format" in message or "response format" in message
