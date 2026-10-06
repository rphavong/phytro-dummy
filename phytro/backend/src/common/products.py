"""Product lookup + store/category browsing with caching (DynamoDB first, OFF second)."""
import re
import urllib.error

from common import config, db, off_client, scoring


def get_product(barcode):
    cached = db.get_cached_product(barcode)
    if cached:
        return cached
    product = off_client.get_product(barcode)
    if product:
        db.put_cached_product(product)
    return product


UPSTREAM_ERRORS = (urllib.error.URLError, TimeoutError)  # HTTPError (e.g. OFF 503) is a URLError


def _all_us(category):
    """'Any US store' list for a category: DynamoDB first; an empty/missing entry is re-fetched (self-healing)."""
    items = db.get_catalog("any", category)
    if not items:
        items = off_client.search(config.CATEGORIES[category]["tag"], None)
        if items:
            db.put_catalog("any", category, items, ttl_hours=24)
    return items or []


def browse(store, category, profile=None, limit=30):
    """Ranked products for a store+category. Returns (products, source, note).

    Order of preference: seeded/cached DynamoDB list -> live Open Food Facts. When a store has
    fewer than 5 tagged items, the 'Any US store' list fills in (marked 'store not confirmed').
    If Open Food Facts is down, whatever is cached is still served.
    """
    if category not in config.CATEGORIES:
        raise ValueError(f"unknown category '{category}'")
    if store not in config.STORES:
        raise ValueError(f"unknown store '{store}'")
    if store == "any":
        return scoring.rank(_all_us(category), profile)[:limit], "catalog", None

    note, error = None, None
    products = db.get_catalog(store, category)
    source = "catalog"
    if products is None:
        try:
            products = off_client.search(config.CATEGORIES[category]["tag"], store)
            source = "open-food-facts"
            db.put_catalog(store, category, products, ttl_hours=24)
        except UPSTREAM_ERRORS as exc:
            products, error = [], exc
    products = [dict(p) for p in products]

    if len(products) < 5:
        # OFF store tagging is crowd-sourced and patchy - fill in with all US products.
        try:
            extra = _all_us(category)
        except UPSTREAM_ERRORS as exc:
            extra, error = [], error or exc
        seen = {p["barcode"] for p in products}
        tagged = len(seen)
        for p in extra:
            if p["barcode"] not in seen:
                products.append({**p, "store_unverified": True})
        if extra:
            note = (f"Only {tagged} item(s) are tagged as sold at {config.STORES[store]} in Open Food Facts, "
                    "so similar US products are included and marked 'store not confirmed'.")
    if not products and error:
        raise error  # nothing cached and the upstream is down -> API returns a friendly 502
    return scoring.rank(products, profile)[:limit], source, note


_WORD = re.compile(r"[a-z0-9]+")
MIN_LOCAL_HITS = 12


def _words(text):
    return _WORD.findall((text or "").lower())


def _relevance(product, terms):
    """Every search word must appear in the name, brand, category or ingredients; name/brand count most."""
    name, brand = set(_words(product.get("name"))), set(_words(product.get("brand")))
    cats = set(_words(" ".join(c.split(":", 1)[-1].replace("-", " ") for c in product.get("categories", []))))
    ingr = set(_words(product.get("ingredients_text")))
    score = 0.0
    for t in terms:
        def has(words):
            return t in words or (len(t) >= 4 and any(w.startswith(t) for w in words))  # "cere" -> cereal
        if has(name):
            score += 3
        elif has(brand):
            score += 2
        elif has(cats):
            score += 1
        elif has(ingr):
            score += 0.5
        else:
            return 0  # a word that matches nothing excludes the product
    return score


def search_by_name(query, store=None, profile=None, limit=40):
    """Find products by name / brand / description. Returns (products, sources, note).

    1. Instant: every product already stored in PhyTro's store/aisle lists (DynamoDB, cached in memory).
    2. If fewer than 12 matches: Open Food Facts full-text search, cached 24 h per query.
    Each result gets its relevance, a PhyTro score for this user, and whether it is listed at `store`.
    """
    q = " ".join(_words(query))[:80]
    if len(q) < 2:
        raise ValueError("type at least 2 letters or digits")
    terms = q.split()
    found, sources, note = {}, [], None

    for p in db.catalog_index().values():
        rel = _relevance(p, terms)
        if rel:
            found[p["barcode"]] = {**p, "relevance": rel}
    if found:
        sources.append("phytro-catalog")

    if len(found) < MIN_LOCAL_HITS:
        remote = db.get_search(q)
        if remote is None:
            try:
                remote = off_client.text_search(q)
                db.put_search(q, remote)
            except UPSTREAM_ERRORS:
                remote = []
                note = ("Open Food Facts is busy right now, so only products already in PhyTro are shown. "
                        "Try again in a minute for more results.")
        if remote:
            sources.append("open-food-facts")
        for p in remote:
            if p["barcode"] not in found:
                # OFF already matched it on full text; still rank our own word matches first
                found[p["barcode"]] = {**p, "listed_at": [], "relevance": _relevance(p, terms) or 0.25}

    results = []
    for p in found.values():
        at = list(p.get("listed_at", []))
        at += [s for s in p.get("store_tags", []) if s in config.STORES and s not in at]
        results.append({**p, "listed_at": at, "at_store": bool(store and store != "any" and store in at)})
    ranked = scoring.rank(results, profile)
    ranked.sort(key=lambda p: (p["at_store"], p["relevance"]), reverse=True)  # stable: ties keep health order
    return ranked[:limit], sources, note


def category_for(product):
    """Map a product to one of PhyTro's UI categories (or None)."""
    cats = set(product.get("categories", []))
    for key, meta in config.CATEGORIES.items():
        if meta["tag"] in cats:
            return key
    return None


def find_alternatives(product, store, profile=None, limit=3):
    """Higher-scoring products from the same category at the same store."""
    category = category_for(product)
    if not category:
        return {"category": None, "alternatives": [],
                "note": "Product category is not one PhyTro tracks yet."}
    ranked, _, note = browse(store if store in config.STORES else "any", category, profile, limit=60)
    mine = scoring.score_product(product, profile)["personal_score"]
    better = [p for p in ranked if p["barcode"] != product["barcode"] and p["phytro"]["personal_score"] > mine]
    slim = [{"barcode": p["barcode"], "name": p["name"], "brand": p["brand"], "image": p["image"],
             "score": p["phytro"]["personal_score"], "grade": p["phytro"]["personal_grade"],
             "why": p["phytro"]["reasons"][:2], "store_unverified": p.get("store_unverified", False)}
            for p in better[:limit]]
    return {"category": category, "your_score": mine, "alternatives": slim, "note": note}
