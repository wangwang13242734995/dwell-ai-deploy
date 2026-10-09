# app/agents/vision_node.py
from __future__ import annotations

from typing import Dict, Any

from app.models.state import AgentState
from app.models.room import RoomObject
from app.vision.config import VisionConfig
from app.vision.router import get_provider
from app.vision.normalize import normalize_objects


def vision_node(state: AgentState) -> Dict[str, Any]:
    """
    Vision Node:
    - Reads state["image_base64"]
    - Produces room_dimensions + objects (VisionOutput)
    - Normalizes objects for downstream constraint/solver
    """
    try:
        cfg = VisionConfig()
        provider = get_provider(cfg)

        image_base64 = state.get("image_base64", "")
        if not image_base64:
            return {"error": "vision_node: image_base64 missing in state", "should_continue": False}

        vision_out = provider.analyze(image_base64)

        room_dims = vision_out.room_dimensions
        objects: list[RoomObject] = vision_out.objects

        locked_ids = state.get("locked_object_ids", [])
        objects = normalize_objects(
            objects=objects,
            room_width=room_dims.width_estimate,
            room_height=room_dims.height_estimate,
            locked_ids=locked_ids,
        )

        return {
            "room_dimensions": room_dims,
            "original_layout": objects,
            "current_layout": objects,
            "explanation": "Vision analysis complete (Gemini).",
            "error": None,
        }

    except Exception as e:
        return {
            "error": f"vision_node failed: {e}",
            "should_continue": False,
        }


# --- Compatibility layer: older route code imports VisionAgent/get_vision_agent ---
class VisionAgent:
    """Async wrapper around vision_node for routes using the class-based API."""

    async def analyze_room(self, image_base64: str):
        from app.models.room import VisionOutput
        result = vision_node({"image_base64": image_base64})
        if result.get("error"):
            raise ValueError(result["error"])
        return VisionOutput(
            room_dimensions=result["room_dimensions"],
            objects=result["original_layout"],
            wall_bounds=None,
            image_width=None,
            image_height=None,
        )


def get_vision_agent() -> VisionAgent:
    return VisionAgent()
