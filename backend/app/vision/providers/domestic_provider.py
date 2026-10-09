# app/vision/providers/domestic_provider.py
"""
国内模型视觉 Provider（走 ai_provider 统一接入层）。

- 使用 LLM_VISION_MODEL（如 qwen-vl-max / glm-4v-plus / hunyuan-vision），
  OpenAI 兼容 chat.completions 的 image_url 多模态输入。
- 复用 gemini_provider 的 JSON 提取逻辑，输出 VisionOutput。
- 未配置 llm_api_key 时抛 ProviderNotConfigured，由 vision/router 走 Gemini 兜底。
"""
from __future__ import annotations

import base64
from typing import Any

from app.core import ai_provider
from app.models.room import VisionOutput
from app.vision.config import VisionConfig
from app.vision.providers.base import VisionProvider
from app.vision.providers.gemini_provider import _ensure_json


def _strip_data_url(b64: str) -> str:
    # supports "data:image/jpeg;base64,...."
    if "," in b64 and b64.strip().lower().startswith("data:"):
        return b64.split(",", 1)[1]
    return b64


class DomesticVisionProvider(VisionProvider):
    """qwen-vl-max / glm-4v 等国内多模态模型，通过 ai_provider.chat_vision 调用。"""

    def __init__(self, cfg: VisionConfig):
        self.cfg = cfg
        if not ai_provider.is_configured():
            raise ai_provider.ProviderNotConfigured(
                "未配置 llm_api_key（国内模型 Provider）。请在 .env 设置 LLM_API_KEY / LLM_BASE_URL / LLM_VISION_MODEL，"
                "或使用 VISION_PROVIDER=gemini 走 Gemini 兜底。"
            )

    def analyze(self, image_base64: str) -> VisionOutput:
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

        text = ai_provider.chat_vision(
            system_prompt="You are a precise room-layout vision extractor. Always return JSON only.",
            user_prompt=prompt,
            image_base64=b64,
            mime_type="image/jpeg",
        )
        data = _ensure_json(text)
        return VisionOutput.model_validate(data)
