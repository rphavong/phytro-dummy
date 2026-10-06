import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../ctx.js";
import { Empty, ProductThumb, ScoreBadge } from "../components/bits.jsx";

const gradeOf = (s) => (s >= 80 ? "Great" : s >= 60 ? "Good" : s >= 40 ? "Fair" : "Poor");

export default function ListPage() {
  const { meta, setListCount } = useApp();
  const [items, setItems] = useState(null);
  const [err, setErr] = useState("");

  const load = () => api.list().then((l) => { setItems(l.items); setListCount(l.items.length); }).catch((e) => setErr(e.message));
  useEffect(() => { load(); }, []);

  const toggle = async (it) => {
    setItems((xs) => xs.map((x) => (x.barcode === it.barcode ? { ...x, checked: !x.checked } : x)));
    await api.saveItem({ ...it, checked: !it.checked });
  };
  const remove = async (it) => {
    setItems((xs) => xs.filter((x) => x.barcode !== it.barcode));
    setListCount((n) => n - 1);
    await api.removeItem(it.barcode);
  };
  const clearChecked = async () => {
    const done = items.filter((i) => i.checked);
    await Promise.all(done.map((i) => api.removeItem(i.barcode)));
    load();
  };

  if (err) return <p className="err">{err}</p>;
  if (!items) return <div className="center-msg"><span className="spinner" /></div>;
  if (!items.length)
    return (
      <Empty icon="📝" title="Your list is empty">
        Browse an aisle in <Link to="/">Shop</Link> and tap <b>+ List</b> on the items you want.
      </Empty>
    );

  const byStore = items.reduce((acc, i) => ((acc[i.store || "any"] ||= []).push(i), acc), {});
  const scored = items.filter((i) => typeof i.score === "number");
  const avg = scored.length ? Math.round(scored.reduce((t, i) => t + i.score, 0) / scored.length) : null;
  const doneCount = items.filter((i) => i.checked).length;

  return (
    <div>
      <div className="row-between">
        <div>
          <h1 className="page-title">My shopping list</h1>
          <p className="muted">{doneCount} of {items.length} in the cart · saved to your account, so it's on your phone too.</p>
        </div>
        <div className="row">
          {avg !== null && <ScoreBadge score={avg} grade={gradeOf(avg)} label="cart avg" />}
          <button className="ghost small" onClick={() => window.print()}>🖨️ Print</button>
          {doneCount > 0 && <button className="ghost small" onClick={clearChecked}>Clear checked</button>}
        </div>
      </div>
      <div className="progress"><div style={{ width: `${(doneCount / items.length) * 100}%` }} /></div>

      {Object.entries(byStore).map(([store, list]) => (
        <section key={store}>
          <h2 className="section-title">🏬 {meta.stores.find((s) => s.id === store)?.label || store}</h2>
          <ul className="product-list">
            {list.map((it) => (
              <li key={it.barcode} className={`card product-row ${it.checked ? "checked" : ""}`}>
                <input type="checkbox" className="big-check" checked={it.checked} onChange={() => toggle(it)}
                       aria-label={`Got ${it.name}`} />
                <Link to={`/product/${it.barcode}?store=${store}`} className="product-link">
                  <ProductThumb src={it.image} alt={it.name} />
                  <div className="grow">
                    <strong>{it.name}</strong>
                    <div className="muted">{it.brand}</div>
                    {it.note && <div className="muted small-text">🤖 {it.note}</div>}
                  </div>
                  {typeof it.score === "number" && <ScoreBadge score={it.score} grade={gradeOf(it.score)} size="sm" />}
                </Link>
                <button className="ghost small" onClick={() => remove(it)} aria-label="Remove">✕</button>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}
