import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../api.js";
import { useApp } from "../ctx.js";

export default function ProfilePage() {
  const { meta, profile, setProfile } = useApp();
  const [form, setForm] = useState(profile);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const welcome = params.get("welcome");

  const toggle = (key, id) => {
    setSaved(false);
    setForm((f) => ({ ...f, [key]: f[key].includes(id) ? f[key].filter((x) => x !== id) : [...f[key], id] }));
  };
  const set = (key, v) => { setSaved(false); setForm((f) => ({ ...f, [key]: v })); };

  const save = async (e) => {
    e.preventDefault();
    setBusy(true);
    const p = await api.saveProfile(form);
    setProfile(p);
    setForm(p);
    setBusy(false);
    setSaved(true);
    if (welcome) navigate("/");
  };

  return (
    <form onSubmit={save} className="profile">
      {welcome && (
        <div className="card welcome">
          <h2>👋 Welcome to PhyTro!</h2>
          <p>Tell us what to watch out for - it takes 30 seconds and we'll remember it on every device.
             You can change it any time from <b>Profile</b>.</p>
        </div>
      )}
      <h1 className="page-title">Your preferences</h1>

      <section className="card">
        <label>What should we call you?
          <input value={form.display_name} maxLength={60} onChange={(e) => set("display_name", e.target.value)} />
        </label>
        <label>Where do you usually shop?
          <select value={form.default_store} onChange={(e) => set("default_store", e.target.value)}>
            {meta.stores.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </select>
        </label>
      </section>

      <section className="card">
        <h3>🚫 Allergies</h3>
        <p className="muted">We'll warn you on every product that contains these - or may contain traces.</p>
        <div className="chips">
          {meta.allergens.map((a) => (
            <button type="button" key={a.id} className={`chip ${form.allergens.includes(a.id) ? "on danger" : ""}`}
                    onClick={() => toggle("allergens", a.id)}>{a.label}</button>
          ))}
        </div>
      </section>

      <section className="card">
        <h3>🙅 Things I avoid</h3>
        <div className="chips">
          {meta.avoid.map((a) => (
            <button type="button" key={a.id} className={`chip ${form.avoid.includes(a.id) ? "on" : ""}`}
                    onClick={() => toggle("avoid", a.id)}>{a.label}</button>
          ))}
        </div>
        <h3>🥗 Diet</h3>
        <div className="chips">
          {meta.diets.map((d) => (
            <button type="button" key={d} className={`chip ${form.diet.includes(d) ? "on" : ""}`}
                    onClick={() => toggle("diet", d)}>{d[0].toUpperCase() + d.slice(1)}</button>
          ))}
        </div>
      </section>

      <section className="card">
        <label className="inline check">
          <input type="checkbox" checked={form.auto_add_best} onChange={(e) => set("auto_add_best", e.target.checked)} />
          Allow the AI Shopper Advocate to add its recommended swap to my list automatically
        </label>
      </section>

      <div className="sticky-save">
        <button className="primary" disabled={busy}>{busy ? "Saving…" : welcome ? "Save & start shopping" : "Save preferences"}</button>
        {saved && <span className="ok">✓ Saved to your account</span>}
      </div>
    </form>
  );
}
