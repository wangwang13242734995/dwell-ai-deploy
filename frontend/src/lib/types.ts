/**
 * TypeScript types matching backend Pydantic schemas
 * 
 * Simplified for Generative Interior Design Agent
 */

export type ObjectType = 'movable' | 'structural';

export interface RoomObject {
  id: string;
  label: string;
  bbox: [number, number, number, number]; // [x, y, width, height] in pixels/percentage
  type: ObjectType;
  orientation: number; // 0=North, 90=East, 180=South, 270=West
  is_locked: boolean;
  // Fields for 3D understanding
  z_index?: number; // 0=floor, 1=furniture, 2=ceiling
  material_hint?: string | null; // wooden, fabric, metal, glass
}

export interface RoomDimensions {
  width_estimate: number;
  height_estimate: number;
}

export interface ConstraintViolation {
  constraint_name: string;
  description: string;
  severity: 'error' | 'warning';
  objects_involved: string[];
}

// === API Request/Response Types ===

export interface AnalyzeRequest {
  image_base64: string;
}

export interface AnalyzeResponse {
  room_dimensions: RoomDimensions;
  objects: RoomObject[];
  wall_bounds: [number, number, number, number] | null;
  message: string;
}

export interface OptimizeRequest {
  current_layout: RoomObject[];
  locked_ids: string[];
  room_dimensions: RoomDimensions;
  max_iterations?: number;
  image_base64?: string;
}

// Layout variation from AI Designer
export interface LayoutVariation {
  name: string; // "Productivity Focus", "Cozy Retreat", "Space Optimized"
  description: string; // Design rationale
  layout: RoomObject[];
  layout_plan?: Record<string, any> | null; // Semantic placement plan from Gemini
  thumbnail_base64?: string | null;
  door_info?: Record<string, any> | null;
  window_info?: Record<string, any> | null;
}

export interface OptimizeResponse {
  variations: LayoutVariation[]; // 2-3 layout options
  message: string;
  new_layout?: RoomObject[] | null;
  explanation?: string | null;
  iterations?: number | null;
  constraint_violations: ConstraintViolation[];
  improvement: number;
}

export interface RenderRequest {
  original_image_base64: string;
  final_layout: RoomObject[];
  original_layout: RoomObject[];
}

export interface RenderResponse {
  image_url: string | null;
  image_base64: string | null;
  message: string;
}

// === Object Icons ===
export const OBJECT_ICONS: Record<string, string> = {
  bed: '🛏️',
  desk: '🪑',
  chair: '💺',
  door: '🚪',
  window: '🪟',
  wardrobe: '🚪',
  nightstand: '🛋️',
  dresser: '🗄️',
  sofa: '🛋️',
  table: '🪑',
  rug: '🟫',
  lamp: '💡',
  closet: '🚪',
  default: '📦'
};

export function getObjectIcon(label: string): string {
  return OBJECT_ICONS[label.toLowerCase()] || OBJECT_ICONS.default;
}

// === App Stage ===
export type AppStage = 'analyze' | 'layouts' | 'perspective' | 'chat' | 'shop';

// === Chat Edit Types ===
export interface ChatEditRequest {
  command: string;
  current_layout: RoomObject[];
  room_dimensions: RoomDimensions;
  current_image_base64?: string;
  layout_plan?: Record<string, any> | null;
}

export interface ChatEditResponse {
  edit_type: 'layout' | 'cosmetic' | 'replace' | 'remove';
  updated_layout: RoomObject[];
  updated_image_base64: string | null;
  explanation: string;
  needs_rerender: boolean;
}

// === Perspective Types ===
export interface PerspectiveRequest {
  layout: RoomObject[];
  room_dimensions: RoomDimensions;
  style?: string;
  view_angle?: string;
  image_base64?: string;
  layout_plan?: Record<string, any> | null;
  door_info?: Record<string, any> | null;
  window_info?: Record<string, any> | null;
}

export interface PerspectiveResponse {
  image_base64: string | null;
  message: string;
}

export interface ShopRequest {
  current_layout: RoomObject[];
  total_budget: number;
  perspective_image_base64?: string;
}

export interface ShopProduct {
  title: string;
  price: number | null;
  price_raw: string;
  link: string;
  thumbnail: string;
  source: string;
  rating: number | null;
  reviews: number | null;
  // 门店 SKU 维度字段（来自门店 SKU 库时存在）
  sku_id?: string | null;
  category?: string | null;
  stock?: number | null;
  lead_time_days?: number | null;
  dimensions?: AdminSkuDimensions | null;
  style?: string | null;
  material?: string | null;
}

export interface ShopItemResult {
  furniture_id: string;
  furniture_label: string;
  search_query: string;
  budget_allocated: number;
  products: ShopProduct[];
  error: string | null;
}

export interface ShopResponse {
  items: ShopItemResult[];
  total_estimated: number;
  total_budget: number;
  message: string;
}

// === P1：SKU 管理后台 Types ===
export interface AdminSkuDimensions {
  w: number | null;
  d: number | null;
  h: number | null;
  unit: string;
}

export interface AdminSkuItem {
  id: string;
  name: string;
  category: string;
  subcategory: string | null;
  material: string | null;
  color: string | null;
  style: string | null;
  dimensions: AdminSkuDimensions;
  price: number;
  stock: number;
  lead_time_days: number;
  space_list: string[];
  image_url: string;
}

export interface AdminSkuListResponse {
  items: AdminSkuItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface AdminCategoryCount {
  category: string;
  count: number;
}

export interface AdminSkuPayload {
  id?: string;
  name: string;
  category: string;
  subcategory?: string;
  material?: string;
  color?: string;
  style?: string;
  dim_w?: number | null;
  dim_d?: number | null;
  dim_h?: number | null;
  unit?: string;
  price: number;
  stock: number;
  lead_time_days?: number;
  space_tags?: string;
  keywords?: string;
  image_url?: string;
}

export interface AdminPriceStockPayload {
  price?: number;
  stock?: number;
  lead_time_days?: number;
}

export interface AdminImportResponse {
  created: number;
  updated: number;
  skipped: number;
  errors: string[];
}

// === P2：报价单 Types ===
export interface QuoteStoreInfo {
  store_name: string;
  store_address: string;
  store_phone: string;
  store_hours: string;
  sales_name: string;
  sales_phone: string;
}

export interface QuoteItem {
  furniture_id: string;
  furniture_label: string;
  product: ShopProduct & {
    sku_id?: string | null;
    category?: string | null;
    stock?: number | null;
    lead_time_days?: number | null;
    dimensions?: { w?: number | null; d?: number | null; h?: number | null; unit?: string } | null;
  };
  quantity: number;
  line_total: number;
  lead_time_days: number;
  in_stock: boolean;
}

export interface QuoteSummary {
  item_count: number;
  total_price: number;
  total_budget: number;
  max_lead_time_days: number;
  in_stock_count: number;
  out_of_stock_count: number;
}

export interface QuotePayload {
  store: QuoteStoreInfo;
  summary: QuoteSummary;
  items: QuoteItem[];
  source_plan: { plan_id: string; created_at: string };
  message?: string;
}

export interface QuoteResponse {
  quote_id: string;
  plan_id: string;
  quote: QuotePayload;
  created_at: string;
}

// === P2：导购跟进线索 Types ===
export type LeadStatus = 'new' | 'following' | 'negotiating' | 'won' | 'lost';

export const LEAD_STATUS_LABELS: Record<LeadStatus, string> = {
  new: '新线索',
  following: '跟进中',
  negotiating: '洽谈中',
  won: '已成交',
  lost: '已流失',
};

export const LEAD_STATUS_COLORS: Record<LeadStatus, string> = {
  new: 'bg-sky-50 text-sky-700 border-sky-200',
  following: 'bg-amber-50 text-amber-700 border-amber-200',
  negotiating: 'bg-violet-50 text-violet-700 border-violet-200',
  won: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  lost: 'bg-neutral-100 text-neutral-500 border-neutral-200',
};

export interface LeadFollowUpRecord {
  content: string;
  created_at: string;
}

export interface LeadItem {
  id: string;
  customer_name: string;
  phone: string;
  store_name: string;
  plan_id: string;
  status: LeadStatus;
  status_label: string;
  remark: string;
  follow_up_records: LeadFollowUpRecord[];
  created_at: string;
  updated_at: string;
}

export interface LeadListResponse {
  items: LeadItem[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface LeadCreatePayload {
  customer_name: string;
  phone?: string;
  store_name?: string;
  plan_id?: string;
  status?: LeadStatus;
  remark?: string;
}

