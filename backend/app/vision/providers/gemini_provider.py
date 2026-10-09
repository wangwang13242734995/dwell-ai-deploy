# app/vision/providers/gemini_provider.py
from __future__ import annotations

import base64
import json
import re
from typing import Any

from app.models.room import VisionOutput
from app.vision.config import VisionConfig
from app.vision.providers.base import VisionProvider


_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _strip_data_url(b64: str) -> str:
    # supports "data:image/jpeg;base64,...."
    if "," in b64 and b64.strip().lower().startswith("data:"):
        return b64.split(",", 1)[1]
    return b64


def _ensure_json(text: str) -> dict[str, Any]:
    """
    Gemini sometimes returns JSON surrounded by text.
    We extract the first {...} block if needed.
    """
    text = (text or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)

    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"Gemini did not return JSON. Got: {text[:200]}...")
    return json.loads(m.group(0))


class GeminiVisionProvider(VisionProvider):
    def __init__(self, cfg: VisionConfig):
        self.cfg = cfg
        # Lazy import so your app doesn’t crash if dependency isn’t installed yet
        try:
            from google import genai  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "google-genai is not installed or import failed. "
                "Install it or switch VISION_PROVIDER."
            ) from e

        # API key mode (simple). Vertex/ADC mode is also possible depending on your setup.
        # If using Vertex via ADC, you can omit api_key and rely on env auth.
        if cfg.gemini_api_key:
            self.client = genai.Client(api_key=cfg.gemini_api_key)
        else:
            raise RuntimeError(
                "Gemini fallback selected but no Gemini credentials configured. "
                "Set GEMINI_API_KEY, or configure domestic provider in .env "
                "(LLM_API_KEY / LLM_BASE_URL / LLM_VISION_MODEL) so VISION_PROVIDER=auto uses it."
            )

    def analyze(self, image_base64: str) -> VisionOutput:
        from google.genai import types  # type: ignore

        b64 = _strip_data_url(image_base64)
        _ = base64.b64decode(b64)  # validate base64 early

        schema_hint = """
Return ONLY valid JSON matching this schema (no markdown, no extra text):
{
  "room_dimensions": { "width_estimate": int, "height_estimate": int },
  "objects": [
    {
      "id": "string",
      "label": "bed|desk|chair|dresser|nightstand|sofa|lamp|door|window|other",
      "bbox": [x, y, width, height],
      "type": "movable|structural",
      "orientation": 0|90|180|270,
      "is_locked": false
    }
  ]
}
Rules:
- bbox is [x,y,width,height] in image pixel coordinates.
- Include doors/windows if visible.
- If unsure about label, use "other".
- Keep object count <= %d.
""" % self.cfg.max_objects

        prompt = f"""
You are a vision extractor for a small bedroom layout planner.
Analyze the room image and produce structured detections for planning.

{schema_hint}
"""

        contents = [
            types.Part.from_text(prompt),
            types.Part.from_bytes(data=base64.b64decode(b64), mime_type="image/jpeg"),
        ]

        resp = self.client.models.generate_content(
            model=self.cfg.gemini_model,
            contents=contents,
        )

        # google-genai responses vary: prefer resp.text
        text = getattr(resp, "text", None)
        if not text:
            # try dig in candidates
            text = str(resp)

        data = _ensure_json(text)
        return VisionOutput.model_validate(data)
