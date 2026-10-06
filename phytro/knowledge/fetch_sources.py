#!/usr/bin/env python3
"""Download PhyTro's validation/knowledge documents into knowledge/raw/.

Run on your laptop (needs internet):
    pip install -r knowledge/requirements.txt
    python knowledge/fetch_sources.py

Each source is saved twice:
  raw/<id>.<pdf|html|xml>   original file, untouched
  raw/<id>.txt              plain text extracted WITHOUT cleaning - headers, footers, menus and legal
                            boilerplate stay in on purpose (the "signal-to-noise" requirement)
If a site blocks the download, the script tells you the URL so you can save the file manually
(browser "Save as...") into knowledge/raw/<id>.pdf or .html and re-run - it will extract existing files.
"""
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
RAW = os.path.join(HERE, "raw")
UA = "Mozilla/5.0 (PhyTro student project; contact via GitHub rphavong)"
ECFR = "https://www.ecfr.gov/api/versioner/v1"


ACCEPT = {"pdf": "application/pdf", "html": "text/html", "xml": "application/xml"}


def download(url, dest, ext):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": ACCEPT[ext]})
    with urllib.request.urlopen(req, timeout=90) as r, open(dest, "wb") as fh:
        fh.write(r.read())


def latest_ecfr_date(title):
    req = urllib.request.Request(f"{ECFR}/titles.json", headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as r:
        titles = json.load(r)["titles"]
    return next(t["latest_issue_date"] for t in titles if t["number"] == title)


def pdf_text(path):
    from pypdf import PdfReader
    reader = PdfReader(path)
    return "\n\n".join(f"--- page {i + 1} ---\n{p.extract_text() or ''}" for i, p in enumerate(reader.pages))


def html_text(path):
    from bs4 import BeautifulSoup
    with open(path, "rb") as fh:
        soup = BeautifulSoup(fh.read(), "html.parser")
    for tag in soup(["script", "style", "noscript"]):  # code is not "text"; menus/footers are kept
        tag.decompose()
    return soup.get_text("\n")


def xml_text(path):
    from bs4 import BeautifulSoup
    with open(path, "rb") as fh:
        return BeautifulSoup(fh.read(), "html.parser").get_text("\n")


def main():
    os.makedirs(RAW, exist_ok=True)
    with open(os.path.join(HERE, "sources.json"), encoding="utf-8") as fh:
        sources = json.load(fh)
    ok, failed = [], []
    for s in sources:
        ext = {"pdf": "pdf", "html": "html", "ecfr": "xml"}[s["kind"]]
        for alt in ("pdf", "html", "xml"):  # a manually saved file of any type wins
            if os.path.exists(os.path.join(RAW, f"{s['id']}.{alt}")):
                ext = alt
        dest = os.path.join(RAW, f"{s['id']}.{ext}")
        try:
            if not os.path.exists(dest):
                if s["kind"] == "ecfr":
                    e = s["ecfr"]
                    date = latest_ecfr_date(e["title"])
                    url = f"{ECFR}/full/{date}/title-{e['title']}.xml?part={e['part']}"
                    if e.get("section"):
                        url += f"&section={e['section']}"
                    s["url"] = url
                else:
                    url = s["url"]
                print(f"↓ {s['id']}  {url}")
                try:
                    download(url, dest, ext)
                except Exception:
                    if s["kind"] != "ecfr":
                        raise
                    # fallback: the human-readable eCFR page
                    e = s["ecfr"]
                    page = f"section-{e['section']}" if e.get("section") else f"part-{e['part']}"
                    url = f"https://www.ecfr.gov/current/title-{e['title']}/{page}"
                    ext, dest = "html", os.path.join(RAW, f"{s['id']}.html")
                    print(f"  ↻ retry as web page {url}")
                    download(url, dest, ext)
                    s["url"] = url
            text = {"pdf": pdf_text, "html": html_text, "xml": xml_text}[ext](dest)
            if len(text.strip()) < 200:
                raise ValueError("extracted text is nearly empty (blocked page or scanned PDF?)")
            with open(os.path.join(RAW, f"{s['id']}.txt"), "w", encoding="utf-8") as fh:
                fh.write(text)
            ok.append((s["id"], len(text)))
        except Exception as exc:  # keep going; report at the end
            if os.path.exists(dest) and os.path.getsize(dest) < 500:
                os.remove(dest)
            failed.append((s["id"], s.get("url", ""), repr(exc)))

    # remember resolved eCFR URLs for citations
    with open(os.path.join(HERE, "sources.json"), "w", encoding="utf-8") as fh:
        json.dump(sources, fh, indent=2)

    print("\n✅ extracted:")
    for i, n in ok:
        print(f"   {i:28s} {n:>9,} chars")
    if failed:
        print("\n⚠️  could not fetch (save manually into knowledge/raw/<id>.pdf|.html, then re-run):")
        for i, url, err in failed:
            print(f"   {i}: {url}\n      {err}")
    print(f"\n{len(ok)}/{len(sources)} documents ready. Next: python knowledge/build_index.py")
    return 0 if len(ok) >= 5 else 1


if __name__ == "__main__":
    sys.exit(main())
