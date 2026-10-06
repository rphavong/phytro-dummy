#!/usr/bin/env python3
"""Chunk knowledge/raw/*.txt and write the BM25 index the Toxicology Analyst searches.

    python knowledge/build_index.py            # -> backend/src/data/kb_index.json
    python knowledge/build_index.py --raw DIR --out FILE
"""
import argparse
import json
import os
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "backend", "src"))
from common.kb import tokenize  # noqa: E402  (same tokenizer at build and query time)

CHUNK, OVERLAP = 1200, 200


def chunks(text):
    text = " ".join(text.split())  # collapse whitespace only - no other cleaning
    i = 0
    while i < len(text):
        yield text[i:i + CHUNK]
        i += CHUNK - OVERLAP


def build(raw_dir, sources_path, out_path):
    with open(sources_path, encoding="utf-8") as fh:
        meta = {s["id"]: s for s in json.load(fh)}
    docs, out_chunks, df = {}, [], Counter()
    for name in sorted(os.listdir(raw_dir)):
        if not name.endswith(".txt"):
            continue
        doc_id = name[:-4]
        m = meta.get(doc_id, {})
        docs[doc_id] = {"title": m.get("title", doc_id), "authority": m.get("authority", "unknown"),
                        "date": m.get("date", "unknown"), "status": m.get("status", "unknown"),
                        "url": m.get("url", "")}
        with open(os.path.join(raw_dir, name), encoding="utf-8") as fh:
            for ch in chunks(fh.read()):
                tf = Counter(tokenize(ch))
                if not tf:
                    continue
                df.update(tf.keys())
                out_chunks.append({"doc": doc_id, "text": ch, "tf": dict(tf), "len": sum(tf.values())})
    avgdl = sum(c["len"] for c in out_chunks) / max(1, len(out_chunks))
    index = {"docs": docs, "chunks": out_chunks, "df": dict(df), "avgdl": avgdl}
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(index, fh, separators=(",", ":"))
    print(f"indexed {len(docs)} documents, {len(out_chunks)} chunks -> {out_path} "
          f"({os.path.getsize(out_path) / 1e6:.1f} MB)")
    return index


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--raw", default=os.path.join(HERE, "raw"))
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--out", default=os.path.join(ROOT, "backend", "src", "data", "kb_index.json"))
    a = ap.parse_args()
    if not os.path.isdir(a.raw):
        sys.exit("knowledge/raw not found - run knowledge/fetch_sources.py first")
    build(a.raw, a.sources, a.out)
