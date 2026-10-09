"""
国内模型 Provider（OpenAI 兼容协议）

统一封装文本补全与视觉理解，可平滑切换：
    DeepSeek   -> base_url=https://api.deepseek.com/v1,   model=deepseek-chat
    通义千问    -> base_url=https://dashscope.aliyuncs.com/compatible-mode/v1, model=qwen-plus / qwen-vl-max
    智谱 GLM    -> base_url=https://open.bigmodel.cn/api/paas/v4,                model=glm-4-plus / glm-4v-plus
    腾讯混元    -> base_url=https://api.hunyuan.cloud.tencent.com/v1,            model=hunyuan-turbo / hunyuan-vision

未配置 llm_api_key 时，各方法返回 None / 抛 ProviderNotConfigured，由调用方走规则降级。
依赖：openai>=1.0（OpenAI SDK 原生支持 OpenAI 兼容端点）。
"""

import base64
import json
import re
from typing import Any, Dict, List, Optional

from app.config import get_settings


class ProviderNotConfigured(Exception):
    """国内模型 Provider 未配置。"""


def _client():
    from openai import OpenAI

    settings = get_settings()
    if not settings.llm_api_key:
        raise ProviderNotConfigured(
            "未配置 llm_api_key（国内模型 Provider）。请在 .env 设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。"
        )
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=60,
    )


def is_configured() -> bool:
    return bool(get_settings().llm_api_key)


def chat_text(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """
    文本补全（规划 / 描述 / JSON 生成）。
    返回模型文本；未配置时抛 ProviderNotConfigured。
    """
    settings = get_settings()
    client = _client()
    model = model or settings.llm_model or "deepseek-chat"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def chat_vision(
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
    mime_type: str = "image/png",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> str:
    """
    视觉理解（户型图 / 房间照）。image_base64 可带 data URL 前缀。
    返回模型文本；未配置时抛 ProviderNotConfigured。
    """
    settings = get_settings()
    client = _client()
    model = model or settings.llm_vision_model or settings.llm_model or "qwen-vl-max"

    clean_b64 = image_base64.split(",")[1] if "," in image_base64 else image_base64
    content: List[Dict[str, Any]] = [
        {"type": "text", "text": user_prompt},
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime_type};base64,{clean_b64}"},
        },
    ]
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": content},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return resp.choices[0].message.content or ""


def encode_image_file(path: str) -> str:
    """读取本地图片并转 base64（无 data URL 前缀）。"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


# ============================================================================
# JSON 辅助：chat_text / chat_vision 的结果统一解析为 dict
# ============================================================================
_JSON_RE = re.compile(r"\{.*\}", re.DOTALL)


def _extract_json(text: str) -> dict:
    text = (text or "").strip()
    if text.startswith("{") and text.endswith("}"):
        return json.loads(text)
    m = _JSON_RE.search(text)
    if not m:
        raise ValueError(f"Model did not return JSON. Got: {text[:200]}...")
    return json.loads(m.group(0))


def chat_text_json(
    system_prompt: str,
    user_prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict:
    """文本补全并要求返回 JSON（自动提取首个 JSON 块）。"""
    return _extract_json(
        chat_text(
            system_prompt, user_prompt, model=model,
            temperature=temperature, max_tokens=max_tokens,
        )
    )


def chat_vision_json(
    system_prompt: str,
    user_prompt: str,
    image_base64: str,
    mime_type: str = "image/png",
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 4096,
) -> dict:
    """视觉理解并要求返回 JSON（自动提取首个 JSON 块）。"""
    return _extract_json(
        chat_vision(
            system_prompt, user_prompt, image_base64, mime_type=mime_type,
            model=model, temperature=temperature, max_tokens=max_tokens,
        )
    )


# ============================================================================
# 生图：通义万相 wanx / 智谱 CogView（OpenAI 兼容 images API）
# ============================================================================
def _image_client():
    settings = get_settings()
    if not settings.llm_api_key:
        raise ProviderNotConfigured(
            "未配置 llm_api_key（国内模型 Provider）。请在 .env 设置 LLM_API_KEY / LLM_BASE_URL / LLM_MODEL。"
        )
    from openai import OpenAI
    return OpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url or None,
        timeout=120,
    )


def generate_image(
    prompt: str,
    image_base64: Optional[str] = None,
    mime_type: str = "image/png",
    model: Optional[str] = None,
    size: str = "1024x1024",
) -> str:
    """
    国内生图（OpenAI 兼容 images API：通义万相 wanx / 智谱 CogView）。

    - 无 image_base64：文生图（client.images.generate）。
    - 带 image_base64：先由视觉模型（qwen-vl-max / glm-4v）把原图提炼为文字描述，
      再与编辑指令一起交给文生图模型生成，返回最终图片 base64（无 data URL 前缀）。
    - 未配置 llm_api_key 时抛 ProviderNotConfigured，由调用方走 Gemini 兜底。

    注意：国内端点（万相 / CogView）无统一 OpenAI 兼容的图生图编辑 API，
    带图场景采用「视觉提炼 -> 文生图」管线，保真度低于 Gemini 原生图编辑。
    """
    settings = get_settings()
    client = _image_client()
    model = model or settings.llm_image_model or settings.llm_model or "cogview-4"

    # 通义万相 compatible-mode 的 size 用 '*' 分隔，如 1024*1024；智谱用 'x'。
    provider = (settings.llm_provider or "").lower()
    size_arg = size
    if provider in ("qwen", "dashscope", "aliyun", "ali", "tongyi") and "*" not in size_arg:
        size_arg = size_arg.replace("x", "*")

    if image_base64:
        clean_b64 = image_base64.split(",")[1] if "," in image_base64 else image_base64
        vision_model = settings.llm_vision_model or settings.llm_model or "qwen-vl-max"
        desc = chat_vision(
            "You are an expert interior/floor-plan visual describer. "
            "Describe the room layout precisely: room dimensions, each furniture item with "
            "position/orientation, door/window locations, style and materials. "
            "Output plain text only, no JSON.",
            "Describe the attached image in detail so an image-generation model can recreate it.",
            clean_b64,
            mime_type=mime_type,
            model=vision_model,
            temperature=0.1,
        )
        combined_prompt = f"{prompt}\n\nORIGINAL ROOM LAYOUT (from visual analysis):\n{desc}"
        resp = client.images.generate(
            model=model, prompt=combined_prompt, size=size_arg, response_format="b64_json"
        )
    else:
        resp = client.images.generate(
            model=model, prompt=prompt, size=size_arg, response_format="b64_json"
        )

    b64 = getattr(resp.data[0], "b64_json", None)
    if not b64:
        raise RuntimeError("Image generation returned no b64_json in response")
    return b64
