"""
Configuration Settings

Environment variables and application configuration.
Includes LangSmith tracing setup for agent observability.
"""

import os
from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App settings
    app_name: str = "Dwell.ai API"
    app_version: str = "2.0.0"
    debug: bool = True
    
    # API settings
    api_prefix: str = "/api/v1"
    
    # CORS
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "http://localhost:3001", "http://127.0.0.1:3001"]
    
    # Optimization defaults
    default_max_iterations: int = 5
    default_door_clearance: float = 60.0
    default_walking_path_width: float = 45.0
    
    # Google AI
    google_api_key: str = ""
    # Vision Analysis (highest reasoning for pixels)
    vision_model_name: str = "gemini-3-pro-preview"
    # Logic/Planning (generating & validating JSON plans)
    planning_model_name: str = "gemini-2.5-pro"
    # Layout Image Generation (image editing for top-down)
    layout_image_model_name: str = "gemini-3-pro-image-preview"
    # Perspective & Chat Image Generation (fast image generation/editing)
    render_image_model_name: str = "gemini-2.5-flash-image"
    
    # 鍥藉唴妯″瀷 Provider锛圤penAI 鍏煎鍗忚锛屽彲鎺?DeepSeek / 閫氫箟鍗冮棶 / 鏅鸿氨GLM / 鑵捐娣峰厓绛夛級
    # 浼樺厛浣跨敤鍥藉唴 Provider锛涙湭閰嶇疆鏃跺洖閫€ Google Gemini
    llm_provider: str = ""           # 绀轰緥: deepseek / qwen / glm / hunyuan / openai
    llm_base_url: str = ""           # 绀轰緥: https://api.deepseek.com/v1
    llm_api_key: str = ""
    llm_model: str = ""              # 鏂囨湰/瑙勫垝妯″瀷锛岀ず渚? deepseek-chat
    llm_vision_model: str = ""       # 瑙嗚妯″瀷锛岀ず渚? qwen-vl-max锛圤penAI 鍏煎 vision锛?    
    llm_image_model: str = ""        # 鍥藉唴鐢熷浘妯″瀷锛岀ず渚? wanx2.1-t2i-turbo / cogview-4
    # LangSmith Tracing
    langchain_tracing_v2: bool = True
    langchain_api_key: str = ""
    langchain_project: str = "my first project"  # Your project name
    langchain_endpoint: str = "https://api.smith.langchain.com"

    serpapi_key: str = ""

    # 闂ㄥ簵 SKU 搴擄紙SQLite锛?
    sku_db_path: str = ""
    
    class Config:
        env_file = (".env", "../.env", "../../.env")
        env_file_encoding = "utf-8"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def setup_langsmith() -> bool:
    """
    Setup LangSmith tracing environment variables.
    
    Call this at application startup to enable tracing.
    Returns True if tracing is enabled, False otherwise.
    """
    settings = get_settings()
    
    if settings.langchain_api_key and settings.langchain_tracing_v2:
        # Set environment variables for LangSmith
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
        os.environ["LANGCHAIN_PROJECT"] = settings.langchain_project
        os.environ["LANGCHAIN_ENDPOINT"] = settings.langchain_endpoint
        
        print(f"鉁?LangSmith tracing enabled!")
        print(f"   Project: {settings.langchain_project}")
        print(f"   Endpoint: {settings.langchain_endpoint}")
        return True
    else:
        print("鈿狅笍  LangSmith tracing NOT configured")
        print("   Set LANGCHAIN_API_KEY in your .env file")
        print("   Get your key at: https://smith.langchain.com -> Settings -> API Keys")
        return False


def get_langsmith_client():
    """
    Get a LangSmith client for manual tracing.
    Returns None if tracing is not configured.
    """
    settings = get_settings()
    
    if not settings.langchain_api_key:
        return None
    
    try:
        from langsmith import Client
        return Client(
            api_key=settings.langchain_api_key,
            api_url=settings.langchain_endpoint
        )
    except ImportError:
        print("鈿狅笍  langsmith package not installed. Run: pip install langsmith")
        return None
