import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../ctx.js";
import { Empty, ProductThumb, ScoreBadge } from "../components/bits.jsx";
import SearchBox from "../components/SearchBox.jsx";

export default function SearchPage() {
  const { meta, profile, setListCount } = useApp();
  const [params, setParams] = useSearchParams();
  const q = params.get("q") || "";
  const store = params.get("store") || profile.default_store;
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [sort, setSort] = useState("match");
  const [added, setAdded] = useState({});

  useEffect(() => {
    if (q.trim().length < 2) return;
    setData(null);
    setErr("");
    api.search(q, store).then(setData).catch((e) => setErr(e.message));
  }, [q, store]);

  useEffect(() => {
    api.list().then((l) => setAdded(Object.fromEntries(l.items.map((i) => [i.barcode, true]))));
  }, []);

  const addToList = async (p) => {
    const at = p.at_store ? store : p.listed_at?.[0] || "any";
    await api.saveItem({ barcode: p.barcode, name: p.name, brand: p.brand, image: p.image, store: at,
                         score: p.phytro.personal_score });
    setAdded((a) => ({ ...a, [p.barcode]: true }));
    setListCount((n) => n + 1);
  };

  const storeLabel = (id) => meta.stores.find((s) => s.id === id)?.label || id;
  const items = [...(data?.products || [])];
  if (sort === "health") items.sort((a, b) => b.phytro.personal_score - a.phytro.personal_score);
  const atStore = items.filter((p) => p.at_store).length;

  return (
    <div>
      <SearchBox big />
      <div className="row-between results-head">
        <div>
          <h1 className="page-title">{q ? <>Results for “{q}”</> : "Search"}</h1>
          {data && (
            <p className="muted">
              {items.length} product{items.length === 1 ? "" : "s"}
              {store !== "any" && ` · ${atStore} listed at ${storeLabel(store)}, shown first`}
            </p>
          )}
        </div>
        <div className="row">
          <label className="inline">Store
            <select value={store} onChange={(e) => { const n = new URLSearchParams(params); n.set("store", e.target.value); setParams(n); }}>
              {meta.stores.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
            </select>
          </label>
          <div className="chips">
            {[["match", "Best match"], ["health", "Healthiest first"]].map(([id, label]) => (
              <button key={id} className={`chip ${sort === id ? "on" : ""}`} onClick={() => setSort(id)}>{label}</button>
            ))}
          </div>
        </div>
      </div>

      {err && <p className="err">⚠️ {err}</p>}
      {!data && !err && q && <div className="center-msg"><span className="spinner" /> Searching…</div>}
      {data?.note && <p className="note">ℹ️ {data.note}</p>}
      {data && items.length === 0 && (
        <Empty icon="🔎" title="No products found">
          Try fewer or different words (e.g. “cheerios” instead of “honey nut cheerios 18 oz”), a brand name,
          or the barcode printed under the stripes.
        </Empty>
      )}

      <ul className="product-list">
        {items.map((p) => (
          <li key={p.barcode} className="card product-row">
            <Link to={`/product/${p.barcode}?store=${store}`} className="product-link">
              <ProductThumb src={p.image} alt={p.name} />
              <div className="grow">
                <strong>{p.name}</strong>
                <div className="muted">{p.brand} {p.quantity && `· ${p.quantity}`}</div>
                <div className="tags">
                  {p.at_store && <span className="tag good">✓ at {storeLabel(store)}</span>}
                  {!p.at_store && p.listed_at?.length > 0 && (
                    <span className="tag">at {p.listed_at.slice(0, 3).map(storeLabel).join(", ")}</span>
                  )}
                  {p.phytro.warnings.slice(0, 2).map((w) => <span key={w.text} className="tag warn">{w.text}</span>)}
                  {p.phytro.flags.slice(0, 2).map((f) => <span key={f.name} className={`tag ${f.level}`}>{f.name}</span>)}
                </div>
              </div>
              <ScoreBadge score={p.phytro.personal_score} grade={p.phytro.personal_grade} />
            </Link>
            <button className={added[p.barcode] ? "ghost small" : "small"} disabled={added[p.barcode]} onClick={() => addToList(p)}>
              {added[p.barcode] ? "✓ On list" : "+ List"}
            </button>
          </li>
        ))}
      </ul>
      {data?.sources?.length > 0 && (
        <p className="muted small-text">Sources: {data.sources.map((s) => (s === "phytro-catalog" ? "PhyTro store lists" : "Open Food Facts search")).join(" + ")}</p>
      )}
    </div>
  );
}
