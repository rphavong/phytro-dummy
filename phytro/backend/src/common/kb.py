"""Regulatory knowledge base: BM25 retrieval over the raw source documents.

knowledge/build_index.py chunks the raw docs in knowledge/raw/ and writes
backend/src/data/kb_index.json, which ships inside the Lambda zip. Retrieval is
pure Python - no vector database to pay for. (Upgrade path: Knowledge Bases for
Bedrock with an S3 Vectors store; see docs/ARCHITECTURE.md.)
"""
import json
import math
import os
import re
from collections import Counter

STOP = set("""a an and are as at be by for from has have in is it its of on or that the this to was were
will with not no shall may any such which under section part than other used use food foods
""".split())
_TOKEN = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")
_INDEX = None
K1, B = 1.5, 0.75


def tokenize(text):
    return [t for t in _TOKEN.findall(text.lower()) if t not in STOP and len(t) > 1]


def _load(path=None):
    global _INDEX
    if _INDEX is None:
        path = path or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "data", "kb_index.json")
        if not os.path.exists(path):
            _INDEX = {"docs": {}, "chunks": [], "df": {}, "avgdl": 1}
        else:
            with open(path, encoding="utf-8") as fh:
                _INDEX = json.load(fh)
    return _INDEX


def search(query, k=4):
    """Return top-k chunks: [{doc_id, title, authority, date, status, url, text, score}]."""
    idx = _load()
    n = len(idx["chunks"])
    if not n:
        return []
    q = Counter(tokenize(query))
    scored = []
    for i, ch in enumerate(idx["chunks"]):
        tf, dl, s = ch["tf"], ch["len"], 0.0
        for term in q:
            f = tf.get(term)
            if not f:
                continue
            df = idx["df"].get(term, 0)
            idf = math.log(1 + (n - df + 0.5) / (df + 0.5))
            s += idf * f * (K1 + 1) / (f + K1 * (1 - B + B * dl / idx["avgdl"]))
        if s > 0:
            scored.append((s, i))
    scored.sort(reverse=True)
    out, per_doc = [], Counter()
    for s, i in scored:
        ch = idx["chunks"][i]
        if per_doc[ch["doc"]] >= 2:  # diversity: max 2 chunks per document
            continue
        per_doc[ch["doc"]] += 1
        meta = idx["docs"][ch["doc"]]
        out.append({"doc_id": ch["doc"], **meta, "text": ch["text"], "score": round(s, 2)})
        if len(out) >= k:
            break
    return out
