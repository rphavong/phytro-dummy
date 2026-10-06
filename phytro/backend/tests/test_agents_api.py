import json

from conftest import COFFEE_BAD, COFFEE_GOOD, FakeBedrock, text, tool_use

from common import bedrock


def _event(route, sub="user-a", body=None, path=None, query=None):
    method = route.split(" ")[0]
    return {"routeKey": route, "requestContext": {"http": {"method": method},
                                                  "authorizer": {"jwt": {"claims": {"sub": sub}}}},
            "body": json.dumps(body) if body is not None else None,
            "pathParameters": path, "queryStringParameters": query}


def _scripted(auto_add=True):
    scout = {"product_name": "Sunrise", "brand": "TestCo", "ingredients": ["instant coffee", "sugar"],
             "additives": [{"code": "E127", "name": "Red 3"}], "allergens": ["milk"], "processing_notes": "",
             "data_gaps": [], "noise_ignored": ["Distributed by TestCo"]}
    analyst = {"findings": [{"ingredient": "Red 3", "concern_level": "high", "summary": "FDA revoked it.",
                             "evidence": [{"doc_id": "fda-red3-2025", "title": "Red 3", "date": "2025-01"}],
                             "conflict": "eCFR listing still shows it until 2027"}],
               "overall_risk": "high", "confidence": "medium", "notes": ""}
    advice = {"verdict": "Consider swapping", "headline": "Swap for a cleaner coffee",
              "explanation": "Contains Red No. 3.", "audit_notes": ["kept Red 3 finding"], "personal_alerts": [],
              "recommended_swap": {"barcode": COFFEE_GOOD["barcode"], "name": "Organic", "reason": "no additives"},
              "added_to_list": True}
    replies = [
        [text("I'll look it up."), tool_use("lookup_product", {"barcode": COFFEE_BAD["barcode"]})],
        [text(json.dumps(scout))],
        [tool_use("search_regulations", {"query": "Red No. 3 revoked"})],
        [text("```json\n" + json.dumps(analyst) + "\n```")],
        [tool_use("find_alternatives", {})],
    ]
    if auto_add:
        replies.append([tool_use("add_to_shopping_list", {"barcode": COFFEE_GOOD["barcode"], "name": "Organic",
                                                          "reason": "cleaner"})])
    replies.append([text(json.dumps(advice))])
    return replies


def test_three_agent_pipeline_end_to_end(ddb, fake_off, monkeypatch):
    from agents import orchestrator
    fake = FakeBedrock(_scripted(auto_add=True))
    monkeypatch.setattr(bedrock, "_client", fake)
    monkeypatch.setattr(bedrock.config, "GUARDRAIL_ID", "gr-test")
    ddb.put_profile("user-a", {"allergens": ["en:milk"], "default_store": "walmart", "auto_add_best": True})
    ddb.create_job("user-a", "job1", COFFEE_BAD["barcode"])

    report = orchestrator.run("user-a", "job1", COFFEE_BAD["barcode"])

    assert report["advice"]["verdict"] == "Consider swapping"
    assert report["analysis"]["findings"][0]["conflict"]
    assert report["alternatives"]["alternatives"][0]["barcode"] == COFFEE_GOOD["barcode"]
    assert report["advice"]["added_to_list"] is True
    assert [i["barcode"] for i in ddb.list_items("user-a")] == [COFFEE_GOOD["barcode"]]  # agent took the action
    assert len(report["usage"]) == 3 and report["total_cost_usd"] > 0
    # guardrail screened the untrusted label text (contained an injection) and the final output
    assert [c["source"] for c in fake.guardrail_calls] == ["INPUT", "OUTPUT"]
    steps = ddb.get_job("user-a", "job1")["steps"]
    kinds = {(s["agent"], s["kind"]) for s in steps}
    assert ("Label Scout", "guardrail") in kinds and ("Toxicology Analyst", "action") in kinds
    assert ("Shopper Advocate", "done") in kinds
    # each agent got its own system prompt
    systems = {c["system"][0]["text"][:30] for c in fake.calls}
    assert len(systems) == 3


def test_add_tool_hidden_when_auto_add_off(ddb, fake_off, monkeypatch):
    from agents import orchestrator
    fake = FakeBedrock(_scripted(auto_add=False))
    monkeypatch.setattr(bedrock, "_client", fake)
    ddb.create_job("user-a", "job2", COFFEE_BAD["barcode"])
    report = orchestrator.run("user-a", "job2", COFFEE_BAD["barcode"], auto_add=False)
    advocate_call = fake.calls[-1]
    names = [t["toolSpec"]["name"] for t in advocate_call["toolConfig"]["tools"]]
    assert names == ["find_alternatives"]
    assert report["advice"]["added_to_list"] is False  # model claimed True; code corrects it
    assert ddb.list_items("user-a") == []


def test_api_profile_is_private_per_user(ddb):
    from handlers import api
    r = api.handler(_event("PUT /profile", "user-a", {"allergens": ["en:peanuts", "bogus"], "default_store": "target",
                                                       "is_admin": True}), None)
    saved = json.loads(r["body"])
    assert saved["allergens"] == ["en:peanuts"] and "is_admin" not in saved
    other = json.loads(api.handler(_event("GET /profile", "user-b"), None)["body"])
    assert other["allergens"] == [] and other["default_store"] == "walmart"


def test_api_requires_auth(ddb):
    from handlers import api
    ev = _event("GET /profile")
    ev["requestContext"]["authorizer"] = {}
    assert api.handler(ev, None)["statusCode"] == 401


def test_api_browse_list_and_analyze(ddb, fake_off, monkeypatch):
    from handlers import api
    r = json.loads(api.handler(_event("GET /browse", query={"store": "walmart", "category": "coffee"}), None)["body"])
    assert r["products"][0]["barcode"] == COFFEE_GOOD["barcode"] and r["source"] == "open-food-facts"
    api.handler(_event("GET /browse", query={"store": "walmart", "category": "coffee"}), None)
    # 1st browse = store search + US fallback (only 2 store-tagged items); 2nd browse = DynamoDB cache
    assert fake_off["search"] == 2
    assert "not confirmed" in r["note"]

    api.handler(_event("PUT /list/{barcode}", body={"name": "Organic", "store": "walmart"},
                       path={"barcode": "0002222222222"}), None)
    items = json.loads(api.handler(_event("GET /list"), None)["body"])["items"]
    assert items[0]["name"] == "Organic"
    api.handler(_event("DELETE /list/{barcode}", path={"barcode": "0002222222222"}), None)

    invoked = {}

    class FakeLambda:
        def invoke(self, **kw):
            invoked.update(kw)

    monkeypatch.setattr(api, "_lambda", FakeLambda())
    r = api.handler(_event("POST /analyze", body={"barcode": "0001111111111"}), None)
    assert r["statusCode"] == 202 and invoked["InvocationType"] == "Event"
    job_id = json.loads(r["body"])["job_id"]
    job = json.loads(api.handler(_event("GET /jobs/{id}", path={"id": job_id}), None)["body"])
    assert job["status"] == "queued"
    assert api.handler(_event("POST /analyze", body={"barcode": "abc"}), None)["statusCode"] == 400


def test_parse_json_handles_fences_and_escapes():
    assert bedrock.parse_json('Sure!\n```json\n{"a": "x \\" }", "b": {"c": 1}}\n```') == {"a": 'x " }', "b": {"c": 1}}


def test_empty_seeded_any_list_self_heals(ddb, fake_off):
    """Regression: a failed seed run used to store an EMPTY 'any' list forever."""
    from common import products
    ddb.put_catalog("any", "coffee", [])  # what the old seeder wrote after 3 failed retries
    items, _, _ = products.browse("any", "coffee")
    assert len(items) == 2 and fake_off["search"] == 1
    assert len(ddb.get_catalog("any", "coffee")) == 2  # repaired in DynamoDB


def test_browse_survives_off_outage(ddb, monkeypatch):
    """OFF returns 503: a store with few tagged items still shows the cached 'any' list."""
    import urllib.error
    from conftest import COFFEE_BAD, COFFEE_GOOD
    from common import off_client, products

    def down(*a, **k):
        raise urllib.error.HTTPError("https://off", 503, "Service Temporarily Unavailable", None, None)

    monkeypatch.setattr(off_client, "search", down)
    ddb.put_catalog("any", "coffee", [COFFEE_BAD, COFFEE_GOOD])
    items, _, note = products.browse("target", "coffee")      # nothing cached for target, OFF down
    assert {p["barcode"] for p in items} == {COFFEE_BAD["barcode"], COFFEE_GOOD["barcode"]}
    assert all(p["store_unverified"] for p in items) and "not confirmed" in note

    from handlers import api                                   # nothing cached at all -> friendly 502
    r = api.handler(_event("GET /browse", query={"store": "kroger", "category": "cereal"}), None)
    assert r["statusCode"] == 502 and "Open Food Facts" in json.loads(r["body"])["error"]


def test_search_by_name_local_first_then_off(ddb, monkeypatch):
    """Name search: stored aisle lists first (instant); Open Food Facts full text only when too few hits."""
    from conftest import COFFEE_BAD, COFFEE_GOOD
    from common import db, off_client, products
    db._catalog_index.update(at=0, items=None)
    ddb.put_catalog("walmart", "coffee", [COFFEE_BAD, COFFEE_GOOD])
    remote_calls = []

    def text_search(q, **k):
        remote_calls.append(q)
        return [{**COFFEE_GOOD, "barcode": "0009999999999", "name": "Organic Decaf Coffee Pods",
                 "store_tags": ["target"]}]

    monkeypatch.setattr(off_client, "text_search", text_search)

    items, sources, note = products.search_by_name("Organic COFFEE!", store="target")
    names = [p["name"] for p in items]
    assert "Organic Whole Bean Coffee" in names and "Organic Decaf Coffee Pods" in names
    assert "Sunrise Flavored Creamer Coffee" not in names        # every word must match ("organic")
    assert items[0]["at_store"] is True and items[0]["barcode"] == "0009999999999"  # sold at Target first
    assert sources == ["phytro-catalog", "open-food-facts"] and note is None
    local = next(p for p in items if p["barcode"] == COFFEE_GOOD["barcode"])
    assert local["listed_at"] == ["walmart"] and "phytro" in local

    products.search_by_name("organic coffee", store="target")   # same query -> cached, no 2nd OFF call
    assert remote_calls == ["organic coffee"]

    hits, _, _ = products.search_by_name("creamer")               # prefix/word match on name
    assert [p["barcode"] for p in hits][0] == COFFEE_BAD["barcode"]


def test_search_survives_off_outage_and_validates(ddb, monkeypatch):
    import urllib.error
    from conftest import COFFEE_GOOD
    from common import db, off_client, products
    from handlers import api
    db._catalog_index.update(at=0, items=None)
    ddb.put_catalog("walmart", "coffee", [COFFEE_GOOD])

    def down(*a, **k):
        raise urllib.error.URLError("503")

    monkeypatch.setattr(off_client, "text_search", down)
    r = json.loads(api.handler(_event("GET /search", query={"q": "whole bean"}), None)["body"])
    assert [p["barcode"] for p in r["products"]] == [COFFEE_GOOD["barcode"]] and "busy" in r["note"]
    assert api.handler(_event("GET /search", query={"q": "?"}), None)["statusCode"] == 400
