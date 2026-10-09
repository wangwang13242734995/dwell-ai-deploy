"""
Shopping Agent Node

Agentic node that:
1. Analyzes the perspective image to describe each furniture item's style
2. Allocates the total room budget across items by importance/size
3. Searches the STORE SKU DATABASE (本地门店 SKU 库) for each item
4. Returns structured product recommendations

替代 SerpAPI：推荐结果全部来自门店真实在售 SKU，保证可成交。
Gemini 仅用于风格分析（可选）：未配置 key 时自动降级为规则匹配。

FULLY TRACED with LangSmith.
"""

import json
import base64
import asyncio
import traceback
from typing import List, Dict, Any, Optional

from app.config import get_settings
from app.core import ai_provider
from app.models.room import RoomObject
from app.store.db import SKUStore, match_label_to_keywords

try:
    from langsmith import traceable
    LANGSMITH_ENABLED = True
except ImportError:
    LANGSMITH_ENABLED = False
    def traceable(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


class ShoppingAgent:
    """
    AI agent that finds real products (store SKU) matching the furniture in a room render.
    """

    def __init__(self):
        settings = get_settings()
        self.sku_store = SKUStore()
        self.google_available = bool(settings.google_api_key)
        self.serp_available = bool(settings.serpapi_key)
        if self.google_available:
            from google import genai
            self.client = genai.Client(api_key=settings.google_api_key)
            self.model = settings.planning_model_name
        if self.serp_available:
            from app.tools.serp_search import SerpSearchTool
            self.search_tool = SerpSearchTool()
        print(f"[ShoppingAgent] Initialized | Provider={'on' if ai_provider.is_configured() else 'off'} | Gemini={'on' if self.google_available else 'off(规则降级)'} | SerpAPI={'on' if self.serp_available else 'off'} | SKU库=on")

    @traceable(
        name="shopping_agent.find_products",
        run_type="chain",
        tags=["shopping", "agent", "pipeline"],
    )
    async def find_products(
        self,
        current_layout: List[RoomObject],
        total_budget: float,
        perspective_image_base64: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Main entry point. Analyzes room, allocates budget, searches products.
        """
        # Step 1: Get only movable furniture
        movable_items = [
            {"id": obj.id, "label": obj.label}
            for obj in current_layout
            if obj.type.value == "movable"
        ]

        print(f"[ShoppingAgent] Movable items: {movable_items}")
        print(f"[ShoppingAgent] Total budget: ${total_budget}")
        print(f"[ShoppingAgent] Has perspective image: {perspective_image_base64 is not None}")

        if not movable_items:
            return {"items": [], "total_estimated": 0, "message": "No movable furniture found."}

        # Step 2: 描述家具 + 分配预算（国内 Provider → Gemini → 规则降级）
        if self.google_available or ai_provider.is_configured():
            item_descriptions = await self._describe_and_allocate(
                movable_items, total_budget, perspective_image_base64
            )
        else:
            item_descriptions = self._describe_rule_based(
                movable_items, total_budget
            )

        print(f"[ShoppingAgent] Descriptions for {len(item_descriptions)} item(s):")
        for desc in item_descriptions:
            print(f"  - {desc.get('id')}: query=\"{desc.get('search_query')}\" budget=${desc.get('budget')}")

        # Step 3: Search for each item in parallel
        search_tasks = [self._search_for_item(item) for item in item_descriptions]
        search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

        # Step 4: Assemble results
        items = []
        total_estimated = 0.0
        for i, result in enumerate(search_results):
            desc = item_descriptions[i]
            if isinstance(result, Exception):
                print(f"[ShoppingAgent] Search FAILED for {desc['id']}: {result}")
                items.append({
                    "furniture_id": desc["id"],
                    "furniture_label": desc["label"],
                    "search_query": desc.get("search_query", ""),
                    "budget_allocated": desc.get("budget", 0),
                    "products": [],
                    "error": str(result),
                })
            else:
                best_price = result[0]["price"] if result and result[0].get("price") else 0
                total_estimated += best_price
                items.append({
                    "furniture_id": desc["id"],
                    "furniture_label": desc["label"],
                    "search_query": desc.get("search_query", ""),
                    "budget_allocated": desc.get("budget", 0),
                    "products": result,
                })

        return {
            "items": items,
            "total_estimated": round(total_estimated, 2),
            "total_budget": total_budget,
            "message": f"Found products for {len([i for i in items if i['products']])} of {len(movable_items)} items.",
        }

    @traceable(
        name="describe_and_allocate",
        run_type="llm",
        tags=["provider", "shopping", "description", "budget"],
    )
    async def _describe_and_allocate(
        self,
        movable_items: List[Dict[str, str]],
        total_budget: float,
        image_base64: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        风格描述 + 预算分配：国内 Provider → Gemini → 规则降级。
        """
        if ai_provider.is_configured():
            try:
                return await self._describe_with_provider(
                    movable_items, total_budget, image_base64
                )
            except Exception as e:
                print(f"[ShoppingAgent] 国内 Provider 调用失败，尝试 Gemini/规则降级: {e}")

        if self.gemini_available:
            try:
                return await self._describe_with_gemini(
                    movable_items, total_budget, image_base64
                )
            except Exception as e:
                print(f"[ShoppingAgent] Gemini 调用失败，规则降级: {e}")

        return self._describe_rule_based(movable_items, total_budget)

    async def _describe_with_provider(
        self,
        movable_items: List[Dict[str, str]],
        total_budget: float,
        image_base64: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        国内模型（OpenAI 兼容）实现：把家具 label 转为门店 SKU 搜索关键词并分配预算。
        """
        item_list_str = json.dumps(movable_items, ensure_ascii=False, indent=2)
        num_items = len(movable_items)
        prompt = f"""你是家具门店的导购选品助手。请把通用家具标签转换成适合在门店 SKU 库检索的中文关键词，并为每件家具分配预算。

总预算：¥{total_budget:,.0f}
家具清单（来自布局方案）：
{item_list_str}

任务：
1. 若提供视角渲染图，额外识别图中可见但不在清单中的家具/软装（如地毯、绿植、灯具、装饰画、抱枕），为新识别项生成 id（以 detected_ 开头）。
2. 为每个物品（原有 + 识别）生成门店检索关键词：主要家具（床/沙发/书桌/衣柜/餐桌）给 2-6 个中文词，包含风格、材质、尺寸；软装（地毯/灯/绿植/装饰画）给 2-4 个词。
3. 在总预算内为每个物品分配预算（元），关键家具优先，软装次之，总和须接近总预算。

只返回 JSON 数组：
[{{"id": "bed_1", "label": "bed", "search_query": "实木双人床 1.8米 原木色", "budget": 6000}}, ...]

规则：
- 原有物品必须全部出现，id 与 label 保持原值。
- 新识别物品 id 以 detected_ 开头，label 用英文小写单词。
- 只返回 JSON 数组，不要输出其他内容。"""

        if image_base64:
            raw = await asyncio.to_thread(
                ai_provider.chat_vision,
                "你是家具门店 AI 导购，输出严格 JSON。",
                prompt,
                image_base64,
                temperature=0.4,
            )
        else:
            raw = await asyncio.to_thread(
                ai_provider.chat_text,
                "你是家具门店 AI 导购，输出严格 JSON。",
                prompt,
                temperature=0.4,
            )
        return self._parse_descriptions(raw, movable_items, total_budget, num_items, "Provider")

    def _parse_descriptions(
        self,
        raw_text: str,
        movable_items: List[Dict[str, str]],
        total_budget: float,
        num_items: int,
        source: str,
    ) -> List[Dict[str, Any]]:
        """统一解析并校验模型返回的 JSON 描述列表。"""
        print(f"[ShoppingAgent] {source} raw response ({len(raw_text)} chars): {raw_text[:500]}")
        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"[ShoppingAgent] ERROR: {source} 返回非 JSON，规则降级: {e}")
            return self._describe_rule_based(movable_items, total_budget)

        if isinstance(result, dict):
            extracted = None
            for key in ("items", "furniture", "results", "data", "furniture_items"):
                if key in result and isinstance(result[key], list):
                    extracted = result[key]
                    break
            if extracted is None and "id" in result and "search_query" in result:
                extracted = [result]
            result = extracted or []

        if not isinstance(result, list) or not result:
            return self._describe_rule_based(movable_items, total_budget)

        for i, item in enumerate(result):
            if not isinstance(item, dict):
                continue
            if "id" not in item and i < len(movable_items):
                item["id"] = movable_items[i]["id"]
            if "label" not in item and i < len(movable_items):
                item["label"] = movable_items[i]["label"]
            if "search_query" not in item:
                item["search_query"] = " ".join(match_label_to_keywords(item.get("label", "furniture"))) or item.get("label", "furniture")
            if "budget" not in item:
                item["budget"] = round(total_budget / max(num_items, 1), 2)

        # 预算归一化：按比例缩放到总预算
        budget_sum = sum(item.get("budget", 0) for item in result if isinstance(item, dict))
        if budget_sum > 0 and abs(budget_sum - total_budget) > total_budget * 0.1:
            scale = total_budget / budget_sum
            for item in result:
                if isinstance(item, dict) and "budget" in item:
                    item["budget"] = round(item["budget"] * scale, 2)

        print(f"[ShoppingAgent] Parsed {len(result)} items from {source}")
        return result

    @traceable(
        name="gemini_describe_and_allocate",
        run_type="llm",
        tags=["gemini", "shopping", "description", "budget"],
    )
    async def _describe_with_gemini(
        self,
        movable_items: List[Dict[str, str]],
        total_budget: float,
        image_base64: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Use Gemini to convert generic labels to specific product queries
        and allocate budget proportionally.

        No fallback — raises on failure so we can debug properly.
        """
        item_list_str = json.dumps(movable_items, indent=2)
        num_items = len(movable_items)

        prompt = f"""You are a furniture shopping assistant. Convert generic furniture labels into specific Google Shopping search queries and allocate a budget.

TOTAL BUDGET: ${total_budget:.2f}

FURNITURE ITEMS (from plan):
{item_list_str}

TASK 1 — Analyze the attached perspective image:
Detect ANY additional furniture or decor items visible in the image that are NOT in the "FURNITURE ITEMS" list above (e.g., rugs, plants, lamps, artwork, pillows).
For each new item found, create a new entry with a unique ID (e.g., "detected_plant_1").

TASK 2 — Write a Google Shopping search query for each item (original + detected):
Generate a Google Shopping search query. The specificity depends on the item category, but MUST always be specific enough to find a real product (never generic).

1. KEY FURNITURE (Bed, Sofa, Desk, Wardrobe, Dining Table):
   - HIGH SPECIFICITY. Include precise style, material, color, size, and defining features.
   - Example: "Bed" → "Queen size walnut platform bed frame" : maximum 6 words

2. SECONDARY FURNITURE (Nightstand, Chair, Coffee Table, Dresser):
   - MODERATE SPECIFICITY. Include style, material, color, and main dimension.
   - Example: "Nightstand" → "White oak bedside table with drawers" : maximum 5 words

3. DECOR / ACCESSORIES (Rug, Lamp, Plant, Artwork):
   - LOW SPECIFICITY. Focus on style, color, type, and size.
   - Example: "Plant" → "Artificial fiddle leaf fig tree" :maximum 4 words

Examples of POOR/GENERIC queries (AVOID THESE): "bed", "blue sofa", "wooden table", "plant".

TASK 3 — Allocate ${total_budget:.2f} across ALL items (original + detected) proportionally:
- Prioritize key furniture (Bed, Sofa, Desk) (~70% of budget divided equally)
- Secondary furniture (Tables, Chairs, Dressers) (~60% of budget )
- Decor/Accessories (Plants, Rugs, Lamps) (~30% of budget)

Total estimated cost MUST sum to exactly plus or minus 10% of ${total_budget:.2f}.

Return ONLY a JSON array with ALL objects (original items + detected items):
[
  {{"id": "bed_1", "label": "bed", "search_query": "queen size walnut platform bed frame", "budget": 500.00}},
  {{"id": "detected_plant_1", "label": "plant", "search_query": "artificial fiddle leaf fig tree 6ft", "budget": 80.00, "is_new": true}}
]

RULES:
- Every original item from the input list MUST appear exactly once.
- "id" and "label" of original items must match EXACTLY.
- For new detected items, use IDs starting with "detected_".
- Total estimated cost MUST sum to exactly plus or minus 10% of ${total_budget:.2f}.
- Return ONLY the JSON array, nothing else."""

        # Build contents
        from google.genai import types
        contents = []
        if image_base64:
            clean_b64 = image_base64.split(",")[1] if "," in image_base64 else image_base64 
            try:
                img_data = base64.b64decode(clean_b64)
                contents.append(types.Part.from_bytes(data=img_data, mime_type="image/png"))
                print(f"[ShoppingAgent] Attached perspective image ({len(img_data)} bytes)")
            except Exception as e:
                print(f"[ShoppingAgent] WARNING: Failed to decode image: {e}")
        contents.append(prompt)

        print(f"[ShoppingAgent] Calling Gemini model={self.model} with {len(contents)} content parts")
        print(f"[ShoppingAgent] Prompt length: {len(prompt)} chars")

        # Call Gemini
        try:
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.4,
                )
            )
        except Exception as e:
            print(f"[ShoppingAgent] ERROR: Gemini API call failed!")
            print(f"[ShoppingAgent] Exception type: {type(e).__name__}")
            print(f"[ShoppingAgent] Exception: {e}")
            print(f"[ShoppingAgent] Traceback:\n{traceback.format_exc()}")
            raise RuntimeError(f"Gemini API call failed: {e}") from e

        # Parse response
        raw_text = response.text
        print(f"[ShoppingAgent] Gemini raw response ({len(raw_text)} chars): {raw_text[:1000]}")

        try:
            result = json.loads(raw_text)
        except json.JSONDecodeError as e:
            print(f"[ShoppingAgent] ERROR: Failed to parse Gemini response as JSON!")
            print(f"[ShoppingAgent] JSONDecodeError: {e}")
            print(f"[ShoppingAgent] Full raw response:\n{raw_text}")
            raise RuntimeError(f"Gemini returned invalid JSON: {e}\nRaw: {raw_text[:500]}") from e

        # Handle Gemini wrapping the array in a dict
        if isinstance(result, dict):
            print(f"[ShoppingAgent] WARNING: Gemini returned dict with keys: {list(result.keys())}")
            # Try to extract the array from common wrapper keys
            extracted = None
            for key in ("items", "furniture", "results", "data", "furniture_items"):
                if key in result and isinstance(result[key], list):
                    extracted = result[key]
                    print(f"[ShoppingAgent] Extracted array from key '{key}' ({len(extracted)} items)")
                    break
            if extracted is None:
                # If dict has the expected item fields, it might be a single item — wrap it
                if "id" in result and "search_query" in result:
                    extracted = [result]
                    print(f"[ShoppingAgent] Wrapped single dict item into list")
                else:
                    raise RuntimeError(f"Gemini returned dict but no extractable array. Keys: {list(result.keys())}. Full response: {raw_text[:500]}")
            result = extracted

        if not isinstance(result, list):
            raise RuntimeError(f"Expected list from Gemini, got {type(result).__name__}: {raw_text[:500]}")

        if len(result) == 0:
            raise RuntimeError(f"Gemini returned empty list. Raw: {raw_text[:500]}")

        print(f"[ShoppingAgent] Parsed {len(result)} items from Gemini")

        # Validate each item has required fields
        for i, item in enumerate(result):
            if not isinstance(item, dict):
                raise RuntimeError(f"Item {i} is not a dict: {item}")
            missing = [k for k in ("id", "label", "search_query", "budget") if k not in item]
            if missing:
                print(f"[ShoppingAgent] WARNING: Item {i} missing fields {missing}: {item}")
                # Try to fill in missing fields from movable_items
                if "id" not in item and i < len(movable_items):
                    item["id"] = movable_items[i]["id"]
                if "label" not in item and i < len(movable_items):
                    item["label"] = movable_items[i]["label"]
                if "search_query" not in item:
                    item["search_query"] = f"{item.get('label', 'furniture')} for home"
                if "budget" not in item:
                    item["budget"] = round(total_budget / num_items, 2)

        # Validate + fix budget sum
        budget_sum = sum(item.get("budget", 0) for item in result)
        print(f"[ShoppingAgent] Budget sum: ${budget_sum:.2f} (expected: ${total_budget:.2f})")

        if abs(budget_sum - total_budget) > 1.0:
            print(f"[ShoppingAgent] WARNING: Budget sum off by ${abs(budget_sum - total_budget):.2f}, rescaling")
            if budget_sum > 0:
                ratio = total_budget / budget_sum
                for item in result:
                    item["budget"] = round(item.get("budget", 0) * ratio, 2)
            # Fix rounding on last item
            new_sum = sum(item["budget"] for item in result)
            diff = round(total_budget - new_sum, 2)
            if result and diff != 0:
                result[0]["budget"] = round(result[0]["budget"] + diff, 2)

        return result

    def _describe_rule_based(
        self,
        movable_items: List[Dict[str, str]],
        total_budget: float,
    ) -> List[Dict[str, Any]]:
        """
        Gemini 不可用时的规则降级：
        按 label 映射为门店品类关键词，预算均分。
        """
        num_items = len(movable_items)
        per_budget = round(total_budget / num_items, 2) if total_budget and num_items else 0
        descriptions = []
        for item in movable_items:
            label = item.get("label", "")
            kws = match_label_to_keywords(label)
            query = " ".join(kws) if kws else label
            descriptions.append({
                "id": item["id"],
                "label": label,
                "search_query": query,
                "budget": per_budget,
            })
        print(f"[ShoppingAgent] Rule-based descriptions for {len(descriptions)} items")
        return descriptions

    @traceable(
        name="search_for_item",
        run_type="tool",
        tags=["sku", "shopping", "search"],
    )
    async def _search_for_item(
        self,
        item: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """
        Search STORE SKU DATABASE for a single item within its allocated budget.
        优先门店 SKU 库；SerpAPI 仅在配置了 key 且 SKU 无结果时作为兜底。
        """
        query = item.get("search_query", "")
        budget = item.get("budget", 500)
        label = item.get("label", "furniture")

        if not query:
            print(f"[ShoppingAgent] WARNING: Empty search query for {item.get('id')}, using label")
            kws = match_label_to_keywords(label)
            query = " ".join(kws) if kws else f"{label} furniture"

        print(f"[ShoppingAgent] SKU search: \"{query}\" (budget: ¥{budget})")

        # 门店 SKU 库优先
        sku_products = self.sku_store.search(
            query=query,
            max_price=budget if budget > 0 else None,
            num_results=3,
            label=label,
        )
        products = [self._normalize_sku(p) for p in sku_products]

        # SKU 库无结果且配置了 SerpAPI 时，降级到在线购物搜索
        if not products and self.serp_available:
            print(f"[ShoppingAgent] SKU 库无结果，SerpAPI 兜底: \"{query}\"")
            products = await self.search_tool.search_shopping(
                query=query,
                max_price=budget,
                num_results=3,
            )
            # 兜底也无结果时按 label 再宽泛搜一次
            if not products:
                broader_query = f"{label}"
                print(f"[ShoppingAgent] No results for \"{query}\", retrying with \"{broader_query}\" (budget +50%)")
                products = await self.search_tool.search_shopping(
                    query=broader_query,
                    max_price=budget * 1.5,
                    num_results=3,
                )

        print(f"[ShoppingAgent] Found {len(products)} products for {item.get('id')}")
        return products

    @staticmethod
    def _normalize_sku(p: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 SKU 库记录规范化为统一产品结构（兼容前端 ProductResult）。
        保留门店维度：sku_id / 库存 / 交付周期 / 尺寸 / 材质 / 风格。
        """
        return {
            "title": p.get("name", ""),
            "price": p.get("price"),
            "price_raw": f"¥{p.get('price', 0):,.0f}" if p.get("price") else "",
            "link": p.get("image_url") or "",
            "thumbnail": p.get("image_url") or "",
            "source": "门店SKU",
            "rating": None,
            "reviews": None,
            "sku_id": p.get("id"),
            "category": p.get("category"),
            "stock": p.get("stock", 0),
            "lead_time_days": p.get("lead_time_days", 0),
            "dimensions": p.get("dimensions"),
            "style": p.get("style"),
            "material": p.get("material"),
        }