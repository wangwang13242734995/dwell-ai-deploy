# app/vision/labels.py
"""
Canonical label set + normalization.

Gemini might say "table" and later YOLO might say "dining table".
We normalize both into the same canonical labels so downstream stays stable.
"""

CANONICAL_LABELS = {
    "bed",
    "desk",
    "chair",
    "dresser",
    "nightstand",
    "sofa",
    "lamp",
    "door",
    "window",
}

# Common synonyms -> canonical labels
LABEL_ALIASES = {
    "table": "desk",
    "workdesk": "desk",
    "couch": "sofa",
    "wardrobe": "dresser",
    "cabinet": "dresser",
    "side table": "nightstand",
    "night stand": "nightstand",
}


STRUCTURAL_LABELS = {"door", "window"}


def normalize_label(label: str) -> str:
    key = (label or "").strip().lower()
    key = key.replace("_", " ").replace("-", " ")
    key = " ".join(key.split())
    return LABEL_ALIASES.get(key, key)
