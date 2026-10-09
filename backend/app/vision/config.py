# app/vision/config.py
from pydantic import BaseModel
import os


class VisionConfig(BaseModel):
    """
    Vision provider configuration.

    Switch providers without touching the LangGraph workflow:
      - "auto" now (default): domestic provider if LLM_API_KEY set, else Gemini
      - "gemini": always Gemini
      - "domestic": always domestic (qwen-vl-max / glm-4v via ai_provider)
      - "yolo" later
    """
    provider: str = os.getenv("VISION_PROVIDER", "auto").lower()

    # Gemini settings (google-genai / Vertex AI compatible patterns)
    gemini_model: str = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-pro")
    gemini_api_key: str | None = os.getenv("GEMINI_API_KEY")  # or Vertex auth via ADC

    # Safety / robustness
    max_objects: int = int(os.getenv("VISION_MAX_OBJECTS", "25"))
