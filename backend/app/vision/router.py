# app/vision/router.py
from __future__ import annotations

from app.core import ai_provider
from app.vision.config import VisionConfig
from app.vision.providers.base import VisionProvider


def get_provider(cfg: VisionConfig) -> VisionProvider:
    if cfg.provider in ("auto", "domestic"):
        # 国内多模态优先（qwen-vl-max / glm-4v）；auto 模式下未配置国内 key 时回落 Gemini
        from app.vision.providers.domestic_provider import DomesticVisionProvider
        if cfg.provider == "domestic" or ai_provider.is_configured():
            return DomesticVisionProvider(cfg)

    if cfg.provider in ("auto", "gemini"):
        from app.vision.providers.gemini_provider import GeminiVisionProvider
        return GeminiVisionProvider(cfg)

    if cfg.provider == "yolo":
        from app.vision.providers.yolo_provider import YoloVisionProvider
        return YoloVisionProvider()
    raise ValueError(f"Unknown VISION_PROVIDER: {cfg.provider}")
