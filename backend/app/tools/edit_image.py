"""
Edit Image Tool

Tools for editing floor plan images and room renders.
Used by Designer Agent for layout previews and Chat Editor for surgical edits.

FULLY TRACED with LangSmith - all Gemini image editing calls are tracked.
"""

import base64
import io
import asyncio
from typing import Optional, List, Dict
from google import genai
from google.genai import types
from PIL import Image

from app.config import get_settings
from app.core import ai_provider

# LangSmith tracing
try:
    from langsmith import traceable
    LANGSMITH_ENABLED = True
except ImportError:
    LANGSMITH_ENABLED = False
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


class EditImageTool:
    """
    Tool for applying edits to floor plan and room images.
    Domestic image provider first (wanx / CogView via ai_provider), Gemini fallback.
    All methods are traced with LangSmith for full observability.
    """
    
    def __init__(self):
        settings = get_settings()
        self.settings = settings
        self.use_domestic = ai_provider.is_configured()
        self.client = None
        if settings.google_api_key:
            self.client = genai.Client(api_key=settings.google_api_key)
        if not self.use_domestic and not self.client:
            raise ValueError(
                "No model provider configured: set LLM_API_KEY (domestic wanx/CogView) "
                "or GOOGLE_API_KEY (Gemini fallback)."
            )
        self.model = settings.render_image_model_name

    @traceable(
        name="edit_image_tool.edit_floor_plan",
        run_type="tool",
        tags=["tool", "image", "floor-plan", "edit"],
        metadata={"description": "Edit floor plan to reposition furniture"}
    )
    async def edit_floor_plan(
        self, 
        base_image: str, 
        furniture_movements: List[Dict],
        style_context: Optional[str] = None
    ) -> str:
        """
        Edit a floor plan image to show furniture in new positions.
        
        Args:
            base_image: Base64 encoded floor plan image
            furniture_movements: List of {name, from_pos, to_pos, rotation} dicts
            style_context: Optional style description (e.g., "Work Focused")
            
        Returns:
            Base64 encoded edited floor plan
            
        TRACED: Full tool execution with movement details.
        """
        if "," in base_image:
            base_image = base_image.split(",")[1]
        
        image_data = base64.b64decode(base_image)
        
        # Build movement instructions
        movement_lines = []
        for move in furniture_movements:
            name = move.get("name", "furniture")
            to_pos = move.get("to_pos", {})
            rotation = move.get("rotation", 0)
            
            pos_desc = f"to position ({to_pos.get('x', 50)}%, {to_pos.get('y', 50)}%)"
            rot_desc = f" rotated {rotation}°" if rotation else ""
            
            movement_lines.append(f"- Move {name.upper()} {pos_desc}{rot_desc}")
        
        movements_text = "\n".join(movement_lines)
        style_text = f"\nLayout Style: {style_context}" if style_context else ""
        
        prompt = f"""Edit this architectural floor plan to reposition furniture.

FURNITURE CHANGES:
{movements_text}
{style_text}

CRITICAL REQUIREMENTS:
1. Maintain the TOP-DOWN 2D floor plan perspective exactly
2. Keep the same visual style, line weights, colors as the original
3. PRESERVE all walls, doors, windows, and room boundaries
4. Move ONLY the furniture items specified above
5. Furniture must not overlap - maintain clear spacing
6. Keep furniture proportions and scale consistent
7. Output should look like a professional architectural drawing

Generate the modified floor plan with furniture repositioned."""

        return await self._call_gemini_edit(image_data, prompt, "floor_plan_edit")

    @traceable(
        name="edit_image_tool.edit_image",
        run_type="tool",
        tags=["tool", "image", "edit", "general"],
        metadata={"description": "Apply general edit instruction to image"}
    )
    async def edit_image(
        self, 
        base_image: str, 
        instruction: str, 
        mask_base64: Optional[str] = None
    ) -> str:
        """
        Apply a general edit to an image based on instruction.
        
        Args:
            base_image: Base64 encoded original image
            instruction: Text instruction for the edit
            mask_base64: Optional base64 mask (unused currently)
            
        Returns:
            Base64 encoded edited image
            
        TRACED: Full tool execution with instruction details.
        """
        if "," in base_image:
            base_image = base_image.split(",")[1]
            
        image_data = base64.b64decode(base_image)
        
        # Detect if this is likely a floor plan or a perspective render
        is_floor_plan = any(kw in instruction.lower() for kw in [
            "floor plan", "top-down", "move the", "reposition", "layout"
        ])
        
        if is_floor_plan:
            prompt = f"""Edit this floor plan image.

INSTRUCTION: {instruction}

REQUIREMENTS:
1. Maintain the top-down 2D floor plan perspective
2. Keep the same visual style and line weights
3. Preserve walls, doors, and windows exactly
4. Apply ONLY the requested change
5. Ensure furniture doesn't overlap

Generate the edited floor plan."""
        else:
            prompt = f"""Edit this interior room image.

INSTRUCTION: {instruction}

REQUIREMENTS:
1. Keep everything else exactly the same
2. Maintain photorealistic quality
3. Preserve lighting and perspective
4. Apply ONLY the requested change

Generate the edited image."""

        edit_type = "floor_plan_edit" if is_floor_plan else "perspective_edit"
        return await self._call_gemini_edit(image_data, prompt, edit_type)

    @traceable(
        name="edit_image_tool.edit_perspective_view",
        run_type="tool",
        tags=["tool", "image", "perspective", "cosmetic"],
        metadata={"description": "Apply cosmetic edits to perspective render"}
    )
    async def edit_perspective_view(
        self,
        base_image: str,
        instruction: str
    ) -> str:
        """
        Apply cosmetic edits to a perspective room render.
        
        Args:
            base_image: Base64 encoded perspective render
            instruction: Edit instruction (style, color, lighting changes)
            
        Returns:
            Base64 encoded edited image
            
        TRACED: Full tool execution for perspective edits.
        """
        if "," in base_image:
            base_image = base_image.split(",")[1]
        
        image_data = base64.b64decode(base_image)
        
        prompt = f"""Edit this interior design photograph.

CHANGE REQUESTED: {instruction}

REQUIREMENTS:
1. Maintain photorealistic quality - this should look like a real photo
2. Keep the same camera angle and perspective
3. Preserve room layout and furniture positions
4. Apply the cosmetic/style change naturally
5. Maintain consistent lighting and shadows

Generate the edited room photograph."""

        return await self._call_gemini_edit(image_data, prompt, "cosmetic_edit")

    @traceable(
        name="image_edit_call",
        run_type="llm",
        tags=["image", "edit", "api-call", "domestic-or-gemini"],
        metadata={"model_type": "image-edit"}
    )
    async def _call_gemini_edit(
        self, 
        image_data: bytes, 
        prompt: str,
        edit_type: str = "general"
    ) -> str:
        """
        Make the actual image edit API call.
        Domestic provider first (visual extraction -> wanx/CogView text-to-image),
        Gemini native image editing as fallback.
        
        TRACED as an LLM call for proper visualization in LangSmith.
        """
        import base64 as _b64
        b64_input = _b64.b64encode(image_data).decode("utf-8")
        try:
            if self.use_domestic:
                try:
                    return await asyncio.to_thread(
                        ai_provider.generate_image, prompt, b64_input, mime_type="image/jpeg",
                    )
                except Exception as e:
                    print(f"[EditImage] Domestic image edit failed, fallback Gemini: {e}")
                    if not self.client:
                        raise RuntimeError(
                            f"Domestic image edit failed and no Gemini fallback configured: {e}"
                        )
            if not self.client:
                raise RuntimeError("No model provider configured: set LLM_API_KEY or GOOGLE_API_KEY.")
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=image_data, mime_type="image/jpeg"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                    temperature=0.5
                )
            )
            
            if response.candidates:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        return base64.b64encode(part.inline_data.data).decode('utf-8')
            
            raise RuntimeError("No image generated in response")
            
        except Exception as e:
            raise RuntimeError(f"Image editing failed ({edit_type}): {str(e)}")

    @traceable(
        name="edit_image_tool.batch_edit",
        run_type="tool",
        tags=["tool", "image", "batch", "edit"],
        metadata={"description": "Apply multiple edits sequentially"}
    )
    async def batch_edit(
        self,
        base_image: str,
        instructions: List[str]
    ) -> str:
        """
        Apply multiple edit instructions sequentially.
        
        Args:
            base_image: Base64 encoded original image
            instructions: List of edit instructions to apply in order
            
        Returns:
            Base64 encoded final edited image
            
        TRACED: Full batch operation with all intermediate steps.
        """
        current_image = base_image
        
        for i, instruction in enumerate(instructions):
            current_image = await self.edit_image(
                base_image=current_image,
                instruction=instruction
            )
        
        return current_image