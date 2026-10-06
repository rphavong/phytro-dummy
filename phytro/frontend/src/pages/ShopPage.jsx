import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../ctx.js";
import { Empty, ProductThumb, ScoreBadge } from "../components/bits.jsx";
import SearchBox from "../components/SearchBox.jsx";

export default function ShopPage() {
  const { meta, profile, setListCount } = useApp();
  const [params, setParams] = useSearchParams();
  const store = params.get("store") || profile.default_store;
  const category = params.get("category") || "";
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [added, setAdded] = useState({});
  const [filter, setFilter] = useState("all");

  useEffect(() => {
    if (!category) return;
    setData(null);
    setErr("");
    api.browse(store, category).then(setData).catch((e) => setErr(e.message));
  }, [store, category]);

  useEffect(() => {
    api.list().then((l) => setAdded(Object.fromEntries(l.items.map((i) => [i.barcode, true]))));
  }, []);

  const set = (k, v) => {
    const next = new URLSearchParams(params);
    next.set(k, v);
    if (k === "store" && !category) next.delete("category");
    setParams(next);
  };

  const addToList = async (p) => {
    await api.saveItem({ barcode: p.barcode, name: p.name, brand: p.brand, image: p.image, store,
                         score: p.phytro.personal_score });
    setAdded((a) => ({ ...a, [p.barcode]: true }));
    setListCount((n) => n + 1);
  };

  const catMeta = meta.categories.find((c) => c.id === category);
  const products = (data?.products || []).filter((p) =>
    filter === "all" ? true : filter === "safe" ? !p.phytro.warnings.length : p.phytro.personal_grade === "Great" || p.phytro.personal_grade === "Good");

  return (
    <div>
      <section className="store-bar">
        <span className="muted">Shopping at</span>
        <div className="chips">
          {meta.stores.map((s) => (
            <button key={s.id} className={`chip ${s.id === store ? "on" : ""}`} onClick={() => set("store", s.id)}>
              {s.label}
            </button>
          ))}
        </div>
      </section>

      {!category ? (
        <>
          <h1 className="page-title">What are you shopping for?</h1>
          <SearchBox big />
          <p className="muted">…or pick an aisle. We rank every item by health score, with your allergies and preferences applied.</p>
          <div className="cat-grid">
            {meta.categories.map((c) => (
              <button key={c.id} className="cat" onClick={() => set("category", c.id)}>
                <span className="emoji">{c.emoji}</span>
                {c.label}
              </button>
            ))}
          </div>
        </>
      ) : (
        <>
          <div className="row-between">
            <div>
              <button className="link" onClick={() => { const n = new URLSearchParams(params); n.delete("category"); setParams(n); }}>
                ← All aisles
              </button>
              <h1 className="page-title">{catMeta?.emoji} {catMeta?.label}</h1>
            </div>
            <div className="chips">
              {[["all", "All"], ["good", "Good & Great only"], ["safe", "No warnings for me"]].map(([id, label]) => (
                <button key={id} className={`chip ${filter === id ? "on" : ""}`} onClick={() => setFilter(id)}>{label}</button>
              ))}
            </div>
          </div>

          {err && <p className="err">{err}</p>}
          {!data && !err && <div className="center-msg"><span className="spinner" /> Ranking products…</div>}
          {data?.note && <p className="note">ℹ️ {data.note}</p>}

          {data && products.length === 0 && (
            <Empty icon="🔍" title="Nothing here yet">Try another store or "Any US store".</Empty>
          )}

          {data && products.length > 0 && (
            <>
              {products.some((p) => p.phytro.personal_score >= 60) && <h2 className="section-title">🏆 Healthiest picks for you</h2>}
              <div className="top-picks">
                {products.filter((p) => p.phytro.personal_score >= 60).slice(0, 3).map((p, i) => (
                  <Link key={p.barcode} to={`/product/${p.barcode}?store=${store}`} className="card pick">
                    <span className="rank">#{i + 1}</span>
                    <ProductThumb src={p.image} alt={p.name} />
                    <div className="grow">
                      <strong>{p.name}</strong>
                      <div className="muted">{p.brand}</div>
                    </div>
                    <ScoreBadge score={p.phytro.personal_score} grade={p.phytro.personal_grade} />
                  </Link>
                ))}
              </div>

              <h2 className="section-title">All {catMeta?.label.toLowerCase()} ({products.length})</h2>
              <ul className="product-list">
                {products.map((p) => (
                  <li key={p.barcode} className="card product-row">
                    <Link to={`/product/${p.barcode}?store=${store}`} className="product-link">
                      <ProductThumb src={p.image} alt={p.name} />
                      <div className="grow">
                        <strong>{p.name}</strong>
                        <div className="muted">{p.brand} {p.quantity && `· ${p.quantity}`}</div>
                        <div className="tags">
                          {p.phytro.warnings.slice(0, 2).map((w) => <span key={w.text} className="tag warn">{w.text}</span>)}
                          {p.phytro.flags.slice(0, 2).map((f) => <span key={f.name} className={`tag ${f.level}`}>{f.name}</span>)}
                          {p.store_unverified && <span className="tag">store not confirmed</span>}
                        </div>
                      </div>
                      <ScoreBadge score={p.phytro.personal_score} grade={p.phytro.personal_grade} />
                    </Link>
                    <button className={added[p.barcode] ? "ghost small" : "small"} disabled={added[p.barcode]}
                            onClick={() => addToList(p)}>
                      {added[p.barcode] ? "✓ On list" : "+ List"}
                    </button>
                  </li>
                ))}
              </ul>
            </>
          )}
        </>
      )}
    </div>
  );
}
