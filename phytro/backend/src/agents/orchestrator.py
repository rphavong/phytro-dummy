"""Orchestrates the 3-agent handoff: Scout -> Analyst -> Advocate (who audits the Analyst).

The orchestrator owns the tools (so it controls what each agent can touch - least privilege
at the application layer) and the deterministic score, and it streams every step to the job
record so the web UI can show live Thinking / Action states.
"""
import json
import time

from agents import prompts
from common import bedrock, db, kb, products, scoring

LOOKUP_SPEC = {
    "name": "lookup_product",
    "description": "Fetch a grocery product's raw label data (ingredients, additives, allergens, "
                   "processing level, nutrition per 100 g) by barcode from the Open Food Facts database.",
    "inputSchema": {"json": {"type": "object", "properties": {
        "barcode": {"type": "string", "description": "6-14 digit barcode"}}, "required": ["barcode"]}},
}
SEARCH_SPEC = {
    "name": "search_regulations",
    "description": "Search PhyTro's library of raw regulatory and scientific documents (FDA, eCFR, "
                   "California OEHHA/Prop 65, EU regulations). Returns the best matching passages with "
                   "doc_id, title, authority, publication date and status (current/superseded).",
    "inputSchema": {"json": {"type": "object", "properties": {
        "query": {"type": "string", "description": "short keyword query, e.g. 'titanium dioxide EU ban'"}},
        "required": ["query"]}},
}
ALT_SPEC = {
    "name": "find_alternatives",
    "description": "Find higher-scoring products in the same category at the shopper's store, "
                   "ranked by PhyTro personal score.",
    "inputSchema": {"json": {"type": "object", "properties": {}}},
}
ADD_SPEC = {
    "name": "add_to_shopping_list",
    "description": "Add a product to the shopper's saved shopping list.",
    "inputSchema": {"json": {"type": "object", "properties": {
        "barcode": {"type": "string"}, "name": {"type": "string"},
        "reason": {"type": "string", "description": "why it was added (shown to the shopper)"}},
        "required": ["barcode", "name"]}},
}


def _slim_for_llm(p):
    keep = ["barcode", "name", "brand", "quantity", "ingredients_text", "additives", "allergens",
            "traces", "nova", "nutriscore", "nutriments", "labels", "analysis_tags"]
    return {k: p.get(k) for k in keep}


def run(sub, job_id, barcode, store=None, auto_add=None):
    """Run the full pipeline. Writes progress to DynamoDB; returns the final report."""
    def step(s):
        db.append_step(sub, job_id, s)

    profile = db.get_profile(sub)
    store = store or profile.get("default_store", "any")
    auto_add = profile.get("auto_add_best", False) if auto_add is None else auto_add
    state = {"product": None, "alternatives": None, "added": None, "sources": {}}
    usage = []

    # ---------------- Agent 1: Label Scout ----------------
    def lookup_product(barcode):
        p = products.get_product(barcode)
        if not p:
            return {"error": f"No product found for barcode {barcode}"}
        # Governance: label text is user-contributed. Screen it for prompt-injection before an LLM reads it.
        cleaned, hit = bedrock.apply_guardrail(p.get("ingredients_text", ""), source="INPUT")
        if hit:
            step({"agent": "Label Scout", "kind": "guardrail",
                  "text": "Guardrail removed instruction-like text from the label data."})
            p = {**p, "ingredients_text": "[removed by guardrail]"}
        state["product"] = p
        return _slim_for_llm(p)

    step({"agent": "Label Scout", "kind": "start", "text": "Reading the product label..."})
    r1 = bedrock.run_agent("Label Scout", prompts.SCOUT, f"Analyze the product with barcode {barcode}.",
                           tools={"lookup_product": (LOOKUP_SPEC, lookup_product)}, on_step=step, job_id=job_id)
    usage.append({"agent": "Label Scout", **{k: r1[k] for k in ("tokens_in", "tokens_out", "latency_s", "cost_usd")}})
    product = state["product"] or products.get_product(barcode)
    if not product:
        raise LookupError(f"Product {barcode} was not found in Open Food Facts.")
    try:
        scout = bedrock.parse_json(r1["text"])
    except ValueError:
        scout = {"product_name": product["name"], "brand": product["brand"], "ingredients": [],
                 "additives": [], "allergens": product["allergens"], "data_gaps": ["Scout reply unparseable"]}
    step({"agent": "Label Scout", "kind": "handoff", "text":
          f"Found {len(scout.get('ingredients', []))} ingredients and {len(scout.get('additives', []))} additives. "
          "Handing off to the Toxicology Analyst."})

    # ---------------- Deterministic score (code, not LLM) ----------------
    score = scoring.score_product(product, profile)

    # ---------------- Agent 2: Toxicology Analyst ----------------
    def search_regulations(query):
        hits = kb.search(query, k=3)
        for h in hits:
            state["sources"][h["doc_id"]] = {k: h.get(k) for k in ("title", "authority", "date", "status", "url")}
        return {"results": [{"doc_id": h["doc_id"], "title": h["title"], "authority": h["authority"],
                             "date": h["date"], "status": h["status"], "passage": h["text"][:900]}
                            for h in hits] or [{"note": "no matching passages"}]}

    step({"agent": "Toxicology Analyst", "kind": "start", "text": "Checking ingredients against regulations..."})
    analyst_input = json.dumps({"scout": scout, "rule_based_flags": score["flags"]}, default=str)
    r2 = bedrock.run_agent("Toxicology Analyst", prompts.ANALYST, analyst_input,
                           tools={"search_regulations": (SEARCH_SPEC, search_regulations)}, on_step=step,
                           job_id=job_id)
    usage.append({"agent": "Toxicology Analyst",
                  **{k: r2[k] for k in ("tokens_in", "tokens_out", "latency_s", "cost_usd")}})
    try:
        analysis = bedrock.parse_json(r2["text"])
    except ValueError:
        analysis = {"findings": [], "overall_risk": "unknown", "confidence": "low",
                    "notes": "Analyst reply unparseable; rule-based flags shown instead."}
    step({"agent": "Toxicology Analyst", "kind": "handoff", "text":
          f"{len(analysis.get('findings', []))} finding(s), overall risk {analysis.get('overall_risk')}. "
          "Sending to the Shopper Advocate for audit."})

    # ---------------- Agent 3: Shopper Advocate (auditor + actor) ----------------
    def find_alternatives():
        state["alternatives"] = products.find_alternatives(product, store, profile)
        return state["alternatives"]

    def add_to_shopping_list(barcode, name, reason=""):
        alts = (state["alternatives"] or {}).get("alternatives", [])
        if barcode not in {a["barcode"] for a in alts} and barcode != product["barcode"]:
            return {"error": "Can only add the analyzed product or one of the found alternatives."}
        match = next((a for a in alts if a["barcode"] == barcode), None)
        item = db.put_list_item(sub, {"barcode": barcode, "name": name, "store": store,
                                      "image": (match or product).get("image", ""),
                                      "score": match["score"] if match else score["personal_score"],
                                      "note": f"Added by PhyTro: {reason}"[:200], "added_by": "agent"})
        state["added"] = item
        return {"ok": True, "added": barcode}

    tools = {"find_alternatives": (ALT_SPEC, find_alternatives)}
    if auto_add:
        tools["add_to_shopping_list"] = (ADD_SPEC, add_to_shopping_list)

    step({"agent": "Shopper Advocate", "kind": "start", "text": "Auditing the analysis and personalizing..."})
    advocate_input = json.dumps({
        "scout": scout, "analyst": analysis,
        "phytro_score": {k: score[k] for k in ("score", "grade", "personal_score", "personal_grade",
                                                  "reasons", "warnings", "high_nutrients")},
        "rule_based_flags": [{k: f[k] for k in ("name", "level", "reason")} for f in score["flags"]],
        "shopper_profile": {k: profile.get(k) for k in ("allergens", "avoid", "diet", "default_store")},
        "store": store,
    }, default=str)
    r3 = bedrock.run_agent("Shopper Advocate", prompts.ADVOCATE, advocate_input, tools=tools, on_step=step,
                           job_id=job_id)
    usage.append({"agent": "Shopper Advocate",
                  **{k: r3[k] for k in ("tokens_in", "tokens_out", "latency_s", "cost_usd")}})
    try:
        advice = bedrock.parse_json(r3["text"])
    except ValueError:
        advice = {"verdict": score["personal_grade"], "headline": "Analysis complete",
                  "explanation": r3["text"][:600], "audit_notes": [], "personal_alerts": []}
    if state["alternatives"] is None:  # make sure the UI always has swaps, even if the model skipped the tool
        state["alternatives"] = products.find_alternatives(product, store, profile)
    advice["added_to_list"] = bool(state["added"])

    # Governance: final user-facing text passes through Bedrock Guardrails.
    shown = f"{advice.get('headline', '')}\n\n{advice.get('explanation', '')}"
    safe, intervened = bedrock.apply_guardrail(shown, source="OUTPUT")
    if intervened:
        advice["headline"], advice["explanation"] = "Safety filter applied", safe
        step({"agent": "Shopper Advocate", "kind": "guardrail", "text": "Guardrail adjusted the final answer."})

    report = {
        "barcode": product["barcode"], "created": int(time.time()), "store": store,
        "product": {k: product.get(k) for k in ("barcode", "name", "brand", "image", "quantity", "nova",
                                                 "nutriscore", "allergens", "ingredients_text")},
        "score": score, "scout": scout, "analysis": analysis, "advice": advice,
        "alternatives": state["alternatives"], "sources": state["sources"], "usage": usage,
        "total_cost_usd": round(sum(u["cost_usd"] for u in usage), 6),
        "disclaimer": "PhyTro is decision support, not medical advice. Data comes from crowd-sourced "
                      "Open Food Facts records and public regulatory documents and may be incomplete.",
    }
    step({"agent": "Shopper Advocate", "kind": "done", "text": advice.get("headline", "Done")})
    return report
