import os
import sys

from conftest import COFFEE_BAD, COFFEE_GOOD

from common import kb, scoring


def test_bad_product_scores_poor_with_flags():
    s = scoring.score_product(COFFEE_BAD)
    assert s["grade"] == "Poor" and s["score"] < 40
    names = {f["name"] for f in s["flags"]}
    assert "Erythrosine (FD&C Red No. 3)" in names
    assert "Partially hydrogenated oil (trans fat)" in names
    assert s["flags"][0]["level"] == "high"  # sorted most severe first
    assert "sugars_100g" in s["high_nutrients"]


def test_good_product_scores_great():
    s = scoring.score_product(COFFEE_GOOD)
    assert s["score"] == 100 and s["grade"] == "Great" and s["flags"] == []


def test_personal_profile_warnings_lower_personal_score():
    profile = {"allergens": ["en:milk", "en:soybeans"], "avoid": ["artificial-dyes", "high-sugar"], "diet": ["vegan"]}
    s = scoring.score_product(COFFEE_BAD, profile)
    kinds = [w["type"] for w in s["warnings"]]
    assert kinds.count("allergen") == 1 and "trace" in kinds and kinds.count("avoid") == 2 and "diet" in kinds
    assert s["personal_score"] <= s["score"]


def test_keyword_match_is_word_bounded():
    p = {**COFFEE_GOOD, "ingredients_text": "bhakti chai spice (cardamom)"}
    assert scoring.flagged_ingredients(p) == []


def test_rank_orders_best_first():
    ranked = scoring.rank([COFFEE_BAD, COFFEE_GOOD])
    assert ranked[0]["barcode"] == COFFEE_GOOD["barcode"]


def test_bm25_index_build_and_search(tmp_path):
    raw = tmp_path / "raw"
    raw.mkdir()
    (raw / "fda-red3.txt").write_text("Skip to main content. FDA revoked the authorization for FD&C Red No. 3 "
                                      "erythrosine in food. Footer: Contact FDA.")
    (raw / "oehha.txt").write_text("Acrylamide in coffee. OEHHA adopted section 25704: no Prop 65 warning "
                                   "required for coffee. Page 3 of 40.")
    srcs = tmp_path / "sources.json"
    srcs.write_text('[{"id":"fda-red3","title":"Red 3","date":"2025-01","status":"current","authority":"FDA"}]')
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "knowledge"))
    import build_index
    out = tmp_path / "kb.json"
    build_index.build(str(raw), str(srcs), str(out))
    kb._INDEX = None
    kb._load(str(out))
    hits = kb.search("Red No. 3 erythrosine revoked")
    assert hits[0]["doc_id"] == "fda-red3" and hits[0]["date"] == "2025-01"
    assert kb.search("acrylamide coffee warning")[0]["doc_id"] == "oehha"
    kb._INDEX = None
