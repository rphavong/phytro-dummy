"""Deterministic PhyTro health score (0-100).

The score is computed in code - never by the LLM - so it is fast, free,
reproducible and explainable. The agents explain and audit it; they do not
invent it.
"""
import json
import os
import re

_HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
with open(os.path.join(_HERE, "data", "risk_table.json"), encoding="utf-8") as fh:
    RISK = json.load(fh)

NOVA_PENALTY = {1: 0, 2: 5, 3: 15, 4: 30}
NUTRI_PENALTY = {"a": 0, "b": 5, "c": 12, "d": 22, "e": 32}
LEVEL_PENALTY = {"high": 15, "moderate": 7, "low": 2}
ADDITIVE_CAP = 40

# Profile "avoid" options -> what they match
AVOID_GROUPS = {
    "artificial-dyes": {"label": "Artificial dyes",
                        "tags": {"en:e102", "en:e104", "en:e110", "en:e122", "en:e124", "en:e127",
                                 "en:e129", "en:e132", "en:e133", "en:e171"}},
    "artificial-sweeteners": {"label": "Artificial sweeteners",
                              "tags": {"en:e950", "en:e951", "en:e954", "en:e955", "en:e962"}},
    "nitrites": {"label": "Nitrites / nitrates", "tags": {"en:e249", "en:e250", "en:e251", "en:e252"}},
    "preservatives-bha-bht": {"label": "BHA / BHT", "tags": {"en:e320", "en:e321"}},
    "emulsifiers": {"label": "Gut-irritating emulsifiers", "tags": {"en:e407", "en:e433", "en:e466"}},
    "palm-oil": {"label": "Palm oil", "analysis": "en:palm-oil"},
    "high-sugar": {"label": "High sugar", "nutrient": "sugars_100g"},
    "high-salt": {"label": "High salt", "nutrient": "salt_100g"},
    "high-sat-fat": {"label": "High saturated fat", "nutrient": "saturated-fat_100g"},
}
DIETS = {"vegan": "en:non-vegan", "vegetarian": "en:non-vegetarian"}

ALLERGENS = {
    "en:milk": "Milk", "en:eggs": "Eggs", "en:fish": "Fish", "en:crustaceans": "Shellfish",
    "en:nuts": "Tree nuts", "en:peanuts": "Peanuts", "en:gluten": "Wheat / gluten",
    "en:soybeans": "Soy", "en:sesame-seeds": "Sesame",
}


def grade(score):
    if score >= 80:
        return "Great"
    if score >= 60:
        return "Good"
    if score >= 40:
        return "Fair"
    return "Poor"


def flagged_ingredients(product):
    """Return a de-duplicated list of concern findings from additive tags + raw ingredient text."""
    found = {}
    for tag in product.get("additives", []):
        hit = RISK["additives"].get(tag)
        if hit:
            found[hit["name"]] = {**hit, "match": tag}
    text = (product.get("ingredients_text") or "").lower()
    for kw, hit in RISK["ingredient_keywords"].items():
        if hit["name"] in found:
            continue
        if re.search(r"(?<![a-z])" + re.escape(kw) + r"(?![a-z])", text):
            found[hit["name"]] = {**hit, "match": kw}
    order = {"high": 0, "moderate": 1, "low": 2}
    return sorted(found.values(), key=lambda f: order[f["level"]])


def score_product(product, profile=None):
    """Score a normalized product. Returns dict with score, grade, reasons, flags, personal warnings."""
    profile = profile or {}
    reasons, score = [], 100

    nova = product.get("nova")
    if nova in NOVA_PENALTY and NOVA_PENALTY[nova]:
        score -= NOVA_PENALTY[nova]
        reasons.append(f"Processing level NOVA {nova} (-{NOVA_PENALTY[nova]})")
    ns = product.get("nutriscore")
    if ns in NUTRI_PENALTY and NUTRI_PENALTY[ns]:
        score -= NUTRI_PENALTY[ns]
        reasons.append(f"Nutri-Score {ns.upper()} (-{NUTRI_PENALTY[ns]})")

    flags = flagged_ingredients(product)
    add_pen = min(ADDITIVE_CAP, sum(LEVEL_PENALTY[f["level"]] for f in flags))
    if add_pen:
        score -= add_pen
        reasons.append(f"{len(flags)} flagged ingredient(s) (-{add_pen})")

    thresholds = RISK["nutrient_thresholds_per_100g"]
    nutr = product.get("nutriments", {})
    high_nutrients = [k for k, limit in thresholds.items()
                      if not k.startswith("_") and isinstance(nutr.get(k), (int, float)) and nutr[k] > limit]

    # ---- Personal checks (from the signed-in user's saved profile) ----
    warnings = []
    for a in profile.get("allergens", []):
        if a in product.get("allergens", []):
            warnings.append({"type": "allergen", "text": f"Contains {ALLERGENS.get(a, a)} (your allergen)"})
        elif a in product.get("traces", []):
            warnings.append({"type": "trace", "text": f"May contain traces of {ALLERGENS.get(a, a)}"})
    tags = set(product.get("additives", []))
    for key in profile.get("avoid", []):
        grp = AVOID_GROUPS.get(key)
        if not grp:
            continue
        hit = (("tags" in grp and tags & grp["tags"])
               or ("analysis" in grp and grp["analysis"] in product.get("analysis_tags", []))
               or ("nutrient" in grp and grp["nutrient"] in high_nutrients))
        if hit:
            warnings.append({"type": "avoid", "text": f"Has something you avoid: {grp['label']}"})
    for diet in profile.get("diet", []):
        if DIETS.get(diet) in product.get("analysis_tags", []):
            warnings.append({"type": "diet", "text": f"Not {diet}"})

    personal = score - 25 * sum(1 for w in warnings if w["type"] in {"allergen", "avoid", "diet"})
    known = sum(x is not None for x in (nova, ns)) + bool(product.get("ingredients_text"))
    score, personal = max(0, min(100, score)), max(0, min(100, personal))
    return {
        "score": score,
        "grade": grade(score),
        "personal_score": personal,
        "personal_grade": grade(personal),
        "reasons": reasons or ["No penalties found"],
        "flags": flags,
        "high_nutrients": high_nutrients,
        "warnings": warnings,
        "data_quality": ["low", "low", "medium", "high"][known],
    }


def rank(products, profile=None):
    """Attach scores and sort best-first (personal score, then data quality)."""
    q = {"high": 2, "medium": 1, "low": 0}
    out = []
    for p in products:
        s = score_product(p, profile)
        out.append({**p, "phytro": s})
    out.sort(key=lambda p: (p["phytro"]["personal_score"], q[p["phytro"]["data_quality"]]), reverse=True)
    return out
