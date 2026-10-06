import { useEffect, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../ctx.js";
import AgentTimeline from "../components/AgentTimeline.jsx";
import { Level, ProductThumb, ScoreBadge } from "../components/bits.jsx";

const NUTRI = { "sugars_100g": "Sugar", "salt_100g": "Salt", "saturated-fat_100g": "Saturated fat", "fat_100g": "Fat" };
const NOVA = { 1: "Unprocessed", 2: "Processed culinary ingredient", 3: "Processed", 4: "Ultra-processed" };

export default function ProductPage() {
  const { barcode } = useParams();
  const [params] = useSearchParams();
  const { profile, meta, setListCount } = useApp();
  const [store, setStore] = useState(params.get("store") || profile.default_store);
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(null);
  const [autoAdd, setAutoAdd] = useState(profile.auto_add_best);
  const [onList, setOnList] = useState(false);
  const poll = useRef(null);

  useEffect(() => {
    setData(null); setErr(""); setJob(null); setReport(null);
    api.product(barcode).then((d) => { setData(d); setReport(d.report); }).catch((e) => setErr(e.message));
    api.list().then((l) => setOnList(l.items.some((i) => i.barcode === barcode)));
    return () => clearInterval(poll.current);
  }, [barcode]);

  const analyze = async () => {
    setReport(null);
    const { job_id } = await api.analyze(barcode, store, autoAdd);
    setJob({ status: "queued", steps: [] });
    clearInterval(poll.current);
    poll.current = setInterval(async () => {
      try {
        const j = await api.job(job_id);
        setJob(j);
        if (j.status === "done" || j.status === "error") {
          clearInterval(poll.current);
          if (j.report) {
            setReport(j.report);
            if (j.report.advice?.added_to_list) api.list().then((l) => setListCount(l.items.length));
          }
        }
      } catch (e) {
        clearInterval(poll.current);
        setErr(e.message);
      }
    }, 1500);
  };

  const add = async (p, score) => {
    await api.saveItem({ barcode: p.barcode, name: p.name, brand: p.brand, image: p.image, store, score });
    if (p.barcode === barcode) setOnList(true);
    api.list().then((l) => setListCount(l.items.length));
  };

  if (err) return <p className="err">⚠️ {err} <Link to="/">Back to shopping</Link></p>;
  if (!data) return <div className="center-msg"><span className="spinner" /> Loading product…</div>;

  const { product: p, phytro: s } = data;
  const running = job && (job.status === "queued" || job.status === "running");

  return (
    <div className="product-page">
      <Link to={data.category ? `/?store=${store}&category=${data.category}` : "/"} className="link">← Back</Link>

      <section className="card hero">
        <ProductThumb src={p.image} alt={p.name} />
        <div className="grow">
          <h1 className="page-title">{p.name}</h1>
          <div className="muted">{p.brand} {p.quantity && `· ${p.quantity}`} · barcode {p.barcode}</div>
          <div className="facts">
            {p.nova && <span className="fact">Processing: <b>{NOVA[p.nova]}</b></span>}
            {p.nutriscore && <span className={`fact ns ns-${p.nutriscore}`}>Nutri-Score <b>{p.nutriscore.toUpperCase()}</b></span>}
            {Object.entries(NUTRI).map(([k, label]) => p.nutriments?.[k] != null && (
              <span key={k} className={`fact ${s.high_nutrients.includes(k) ? "hi" : ""}`}>
                {label}: <b>{p.nutriments[k]} g</b>/100 g{s.high_nutrients.includes(k) && " ⬆"}
              </span>
            ))}
          </div>
          <div className="actions">
            <button className={onList ? "ghost" : "primary"} disabled={onList} onClick={() => add(p, s.personal_score)}>
              {onList ? "✓ On your list" : "+ Add to shopping list"}
            </button>
          </div>
        </div>
        <div className="score-col">
          <ScoreBadge score={s.personal_score} grade={s.personal_grade} size="lg" />
          <small className="muted">for you · general {s.score}</small>
          <small className="muted">data quality: {s.data_quality}</small>
        </div>
      </section>

      {s.warnings.length > 0 && (
        <section className="card alert">
          <h3>⚠️ Heads up, based on your profile</h3>
          <ul>{s.warnings.map((w) => <li key={w.text}>{w.text}</li>)}</ul>
        </section>
      )}

      <section className="grid-2">
        <div className="card">
          <h3>Flagged ingredients</h3>
          {s.flags.length === 0 ? <p className="ok">✅ No ingredients from PhyTro's watch-list found.</p> : (
            <ul className="flags">
              {s.flags.map((f) => (
                <li key={f.name}><Level level={f.level} /> <b>{f.name}</b><div className="muted">{f.reason} <i>({f.source})</i></div></li>
              ))}
            </ul>
          )}
          <h4>Why this score</h4>
          <ul className="muted">{s.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
        </div>
        <div className="card">
          <h3>Ingredients (as printed)</h3>
          <p className="ingredients">{p.ingredients_text || "No ingredient list in the database for this product."}</p>
        </div>
      </section>

      <section className="card ai">
        <div className="row-between">
          <div>
            <h2>🤖 Deep AI analysis</h2>
            <p className="muted">Three AI agents work together: one reads the label, one checks regulations, one audits the result for you.</p>
          </div>
          <div className="ai-controls">
            <label className="inline">Store for swaps
              <select value={store} onChange={(e) => setStore(e.target.value)}>
                {meta.stores.map((st) => <option key={st.id} value={st.id}>{st.label}</option>)}
              </select>
            </label>
            <label className="inline check">
              <input type="checkbox" checked={autoAdd} onChange={(e) => setAutoAdd(e.target.checked)} />
              Let the agent add the best swap to my list
            </label>
            <button className="primary" onClick={analyze} disabled={running}>
              {running ? "Agents working…" : report ? "↻ Re-run analysis" : "Run AI analysis"}
            </button>
          </div>
        </div>

        {job && <AgentTimeline steps={job.steps} status={job.status} />}
        {report && <Report report={report} onAdd={add} />}
      </section>
    </div>
  );
}

function Report({ report, onAdd }) {
  const { meta } = useApp();
  const storeLabel = meta.stores.find((x) => x.id === report.store)?.label || report.store;
  const a = report.advice || {};
  const tone = { "Good choice": "great", "OK in moderation": "fair", "Consider swapping": "poor", "Avoid for you": "poor" }[a.verdict] || "fair";
  const alts = report.alternatives?.alternatives || [];
  return (
    <div className="report">
      <div className={`verdict ${tone}`}>
        <span className="verdict-label">{a.verdict}</span>
        <h3>{a.headline}</h3>
        <p>{a.explanation}</p>
        {a.added_to_list && <p className="ok">📝 The Shopper Advocate added its recommended swap to your list.</p>}
      </div>

      {a.personal_alerts?.length > 0 && (
        <div className="card alert"><b>For you:</b><ul>{a.personal_alerts.map((x) => <li key={x}>{x}</li>)}</ul></div>
      )}

      <h3>Findings from the Toxicology Analyst</h3>
      {(report.analysis?.findings || []).length === 0 && <p className="muted">No ingredient-level concerns found.</p>}
      <ul className="findings">
        {(report.analysis?.findings || []).map((f, i) => (
          <li key={i} className="card">
            <div className="row-between"><b>{f.ingredient}</b><Level level={f.concern_level} /></div>
            <p>{f.summary}</p>
            {f.conflict && <p className="conflict">⚖️ Sources disagree: {f.conflict}</p>}
            {f.evidence?.length > 0 && (
              <div className="muted small-text">Sources: {f.evidence.map((e) => {
                const src = report.sources?.[e.doc_id];
                return src?.url
                  ? <a key={e.doc_id} href={src.url} target="_blank" rel="noreferrer">{e.title || src.title} ({e.date || src.date})</a>
                  : <span key={e.doc_id}>{e.title} ({e.date}) </span>;
              }).reduce((acc, el, idx) => (idx ? [...acc, " · ", el] : [el]), [])}</div>
            )}
          </li>
        ))}
      </ul>

      {a.audit_notes?.length > 0 && (
        <details className="audit">
          <summary>🧾 Auditor notes ({a.audit_notes.length})</summary>
          <ul>{a.audit_notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </details>
      )}

      <h3>🔁 Healthier options{storeLabel ? ` at ${storeLabel}` : ""}</h3>
      {alts.length === 0 ? <p className="muted">{report.alternatives?.note || "This is already one of the best options we know of."}</p> : (
        <ul className="product-list">
          {alts.map((alt) => (
            <li key={alt.barcode} className="card product-row">
              <Link to={`/product/${alt.barcode}?store=${report.store}`} className="product-link">
                <ProductThumb src={alt.image} alt={alt.name} />
                <div className="grow">
                  <strong>{alt.name}</strong>
                  <div className="muted">{alt.brand}{alt.store_unverified && " · store not confirmed"}</div>
                  <div className="muted small-text">{alt.why?.join(" · ")}</div>
                </div>
                <ScoreBadge score={alt.score} grade={alt.grade} />
              </Link>
              <button className="small" onClick={() => onAdd(alt, alt.score)}>+ List</button>
            </li>
          ))}
        </ul>
      )}

      <details className="audit">
        <summary>⚙️ Run details (cost &amp; tokens)</summary>
        <table className="usage">
          <thead><tr><th>Agent</th><th>Tokens in</th><th>Tokens out</th><th>Seconds</th><th>Est. cost</th></tr></thead>
          <tbody>
            {report.usage?.map((u) => (
              <tr key={u.agent}><td>{u.agent}</td><td>{u.tokens_in}</td><td>{u.tokens_out}</td><td>{u.latency_s}</td><td>${u.cost_usd.toFixed(5)}</td></tr>
            ))}
          </tbody>
        </table>
        <p className="muted small-text">Total ≈ ${report.total_cost_usd?.toFixed(5)} · {report.disclaimer}</p>
      </details>
    </div>
  );
}
