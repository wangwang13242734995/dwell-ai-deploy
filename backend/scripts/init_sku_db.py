"""
初始化门店 SKU 数据库

用法（backend 目录下）：
    python scripts/init_sku_db.py            # 用内置示例数据重建 sku.db
    python scripts/init_sku_db.py --csv data/seed.csv   # 从 CSV 导入（表头见文件内示例）

CSV 字段（表头）：
    id,name,category,subcategory,material,color,style,dim_w,dim_d,dim_h,unit,price,stock,lead_time_days,space_tags,keywords,image_url
说明：
    - 覆盖式重建，仅操作 backend/data/sku.db，不影响其他文件。
    - price 为人民币售价；stock 为库存；lead_time_days 为交付周期（天）。
    - space_tags 用竖线分隔多个适用空间（如 "客厅|卧室"）。
"""

import csv
import os
import sqlite3
import sys

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BACKEND_DIR, "data", "sku.db")

SCHEMA = """
CREATE TABLE products (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    subcategory TEXT,
    material TEXT,
    color TEXT,
    style TEXT,
    dim_w REAL, dim_d REAL, dim_h REAL,
    unit TEXT DEFAULT 'cm',
    price REAL NOT NULL,
    stock INTEGER DEFAULT 0,
    lead_time_days INTEGER DEFAULT 7,
    space_tags TEXT,
    keywords TEXT,
    image_url TEXT DEFAULT ''
)
"""

SEED = [
    # (id, name, category, subcategory, material, color, style, w, d, h, unit, price, stock, lead, spaces, keywords, image_url)
    ("SKU-SF-001","云朵三人位布艺沙发 2.4m","客厅","沙发","科技布","米白","现代简约",240,95,85,"cm",4280,12,7,"客厅|沙发区","三人位沙发 布艺 科技布 现代 米白 2.4米",""),
    ("SKU-SF-002","真皮电动三人沙发 纳帕皮","客厅","沙发","头层牛皮","深咖","意式轻奢",230,100,88,"cm",12800,5,15,"客厅|沙发区","真皮沙发 电动 头层牛皮 意式 深咖",""),
    ("SKU-SF-003","L型贵妃榻布艺沙发 可拆洗","客厅","沙发","棉麻布","浅灰","北欧",280,160,82,"cm",5680,8,10,"客厅|沙发区","L型沙发 贵妃榻 棉麻 北欧 浅灰",""),
    ("SKU-SF-004","单人休闲沙发 千鸟格","客厅","单人沙发","绒布","千鸟格黑","复古轻奢",78,72,80,"cm",1580,15,7,"客厅|书房|卧室","单人沙发 休闲椅 千鸟格 绒布",""),
    ("SKU-SF-005","岩板圆形茶几 双层","客厅","茶几","岩板+铁艺","爵士白","现代",90,90,42,"cm",1680,20,7,"客厅","茶几 岩板 圆形 双层 现代",""),
    ("SKU-SF-006","胡桃木电视柜 悬浮式 2.2m","客厅","电视柜","实木胡桃木","深棕","新中式",220,42,45,"cm",3980,6,15,"客厅","电视柜 胡桃木 悬浮 实木 新中式",""),
    ("SKU-SF-007","玻璃边几 金属框架","客厅","边几","钢化玻璃+金属","金色","轻奢",45,45,55,"cm",680,25,5,"客厅|卧室","边几 玻璃 金属 轻奢",""),
    ("SKU-SF-008","落地灯 钓鱼灯 大理石底座","客厅","灯具","金属+大理石","黑色","现代简约",40,40,175,"cm",1280,18,7,"客厅|卧室|书房","落地灯 钓鱼灯 大理石 现代",""),
    ("SKU-BD-001","实木床 1.8米 榉木排骨架","卧室","床","榉木实木","原木色","日式原木",188,210,108,"cm",4680,10,15,"卧室|主卧","床 1.8米 实木 榉木 日式 原木",""),
    ("SKU-BD-002","意式极简双人床 1.8米 软包靠背","卧室","床","头层牛皮+实木","暖灰","意式极简",188,212,110,"cm",8980,4,20,"卧室|主卧","床 1.8米 意式 极简 软包 牛皮",""),
    ("SKU-BD-003","儿童床 1.5米 环保松木","卧室","床","松木实木","白色","儿童北欧",158,205,95,"cm",3180,8,10,"卧室|儿童房","儿童床 1.5米 松木 环保 白色",""),
    ("SKU-BD-004","乳胶床垫 1.8米 独立弹簧","卧室","床垫","乳胶+弹簧","白色","护脊",180,200,22,"cm",3280,20,7,"卧室","床垫 乳胶 独立弹簧 1.8米 护脊",""),
    ("SKU-BD-005","床头柜 双层抽屉 实木","卧室","床头柜","橡胶木实木","原木色","日式",45,40,52,"cm",880,30,7,"卧室","床头柜 实木 抽屉 日式 原木",""),
    ("SKU-BD-006","斗柜 六抽 简约 1.2m","卧室","斗柜","中纤板贴皮","奶油白","奶油风",120,42,95,"cm",1980,12,7,"卧室|玄关|客厅","斗柜 六抽 抽屉柜 奶油风 白色",""),
    ("SKU-BD-007","梳妆台 带LED化妆镜","卧室","梳妆台","板材+金属","奶咖","轻奢",100,45,150,"cm",2280,9,10,"卧室","梳妆台 化妆镜 LED 轻奢",""),
    ("SKU-BD-008","衣柜 移门 2.4米 四门","卧室","衣柜","颗粒板E0","胡桃色","现代简约",240,60,220,"cm",4680,6,15,"卧室|衣帽间","衣柜 移门 四门 2.4米 E0级",""),
    ("SKU-DN-001","实木餐桌 1.4米 可伸缩","餐厅","餐桌","橡胶木实木","原木色","日式",140,80,75,"cm",2380,14,10,"餐厅|餐厨区","餐桌 1.4米 实木 可伸缩 日式",""),
    ("SKU-DN-002","岩板餐桌 1.6米 6人位","餐厅","餐桌","岩板+碳素钢","哑光黑","现代简约",160,90,75,"cm",3980,8,10,"餐厅|餐厨区","餐桌 1.6米 岩板 6人 现代",""),
    ("SKU-DN-003","餐椅 软包 实木框架","餐厅","餐椅","布艺+实木","浅灰","北欧",48,52,88,"cm",480,60,7,"餐厅|书房","餐椅 软包 实木 北欧",""),
    ("SKU-DN-004","餐边柜 1.2米 储物柜","餐厅","餐边柜","实木+玻璃","胡桃木色","新中式",120,42,85,"cm",2980,7,15,"餐厅","餐边柜 储物柜 新中式 胡桃木",""),
    ("SKU-WK-001","升降书桌 电动 1.4米","书房","书桌","板材+铝合金","原木色","人体工学",140,70,75,"cm",2580,11,10,"书房|办公区","书桌 电动升降 人体工学 1.4米",""),
    ("SKU-WK-002","简约书桌 实木 1.2米","书房","书桌","橡胶木实木","胡桃色","简约",120,60,75,"cm",1580,16,7,"书房|办公区","书桌 实木 1.2米 简约",""),
    ("SKU-WK-003","人体工学椅 网布 可躺","书房","书椅","网布+尼龙","黑色","人体工学",68,68,120,"cm",1380,25,7,"书房|办公区","人体工学椅 网布 可躺 办公椅",""),
    ("SKU-WK-004","书架 开放式 六层 1.0m","书房","书架","实木框架","原木色","日式",100,30,190,"cm",1580,10,10,"书房|客厅","书架 开放式 六层 实木",""),
    ("SKU-WK-005","文件柜 钢制 三层抽屉","书房","文件柜","冷轧钢板","白色","简约",90,45,110,"cm",980,15,5,"书房","文件柜 钢制 抽屉 三层",""),
    ("SKU-EN-001","鞋柜 翻门 1.0米 带感应灯","玄关","鞋柜","板材E0","暖白","现代简约",100,35,110,"cm",1580,18,7,"玄关","鞋柜 翻门 感应灯 1米",""),
    ("SKU-EN-002","换鞋凳 软包 实木腿","玄关","换鞋凳","布艺+实木","米白","简约",90,38,45,"cm",680,22,5,"玄关|卧室","换鞋凳 软包 实木",""),
    ("SKU-EN-003","玄关桌 半圆 金属框架","玄关","玄关桌","岩板+金属","金色","轻奢",90,30,80,"cm",1280,12,7,"玄关|客厅","玄关桌 半圆 岩板 轻奢",""),
    ("SKU-SO-001","羊毛混纺地毯 2m×3m","软装","地毯","羊毛混纺","奶油色","现代",200,300,1,"cm",1680,20,7,"客厅|卧室","地毯 羊毛 2x3米 奶油色",""),
    ("SKU-SO-002","窗帘 高精密遮光 成品帘","软装","窗帘","高精密面料","雾霾蓝","简约",280,0,250,"cm",1280,30,7,"客厅|卧室","窗帘 遮光 高精密 成品",""),
    ("SKU-SO-003","装饰画 抽象 三联组","软装","装饰画","画布+木框","莫兰迪色","现代",60,3,90,"cm",480,40,5,"客厅|卧室|书房","装饰画 三联 抽象 莫兰迪",""),
    ("SKU-SO-004","仿真绿植 琴叶榕 1.6m","软装","绿植","PE仿真","绿色","北欧",40,40,160,"cm",380,35,3,"客厅|玄关|书房","仿真绿植 琴叶榕 北欧 1.6米",""),
    ("SKU-SO-005","抱枕 靠垫 45×45 四件套","软装","抱枕","绒布","暖咖","简约",45,45,15,"cm",198,50,3,"客厅|卧室","抱枕 靠垫 四件套 绒布",""),
]


def rebuild(rows):
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS products")
    cur.execute(SCHEMA)
    cur.executemany(
        "INSERT INTO products VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", rows
    )
    conn.commit()
    cur.execute("SELECT COUNT(*) FROM products")
    total = cur.fetchone()[0]
    conn.close()
    print(f"[init_sku_db] 重建完成：{DB_PATH}")
    print(f"[init_sku_db] 共 {total} 条商品")
    return total


def from_csv(path):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append((
                r["id"], r["name"], r["category"], r.get("subcategory", ""),
                r.get("material", ""), r.get("color", ""), r.get("style", ""),
                float(r.get("dim_w") or 0), float(r.get("dim_d") or 0), float(r.get("dim_h") or 0),
                r.get("unit", "cm"), float(r["price"]), int(r.get("stock") or 0),
                int(r.get("lead_time_days") or 7), r.get("space_tags", ""),
                r.get("keywords", ""), r.get("image_url", ""),
            ))
    return rows


if __name__ == "__main__":
    if "--csv" in sys.argv:
        idx = sys.argv.index("--csv")
        csv_path = sys.argv[idx + 1]
        if not os.path.isabs(csv_path):
            csv_path = os.path.join(BACKEND_DIR, csv_path)
        rows = from_csv(csv_path)
        print(f"[init_sku_db] 从 CSV 导入 {len(rows)} 条")
    else:
        rows = SEED
        print("[init_sku_db] 使用内置示例数据")
    rebuild(rows)
