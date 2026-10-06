import { useState } from "react";
import { auth } from "../api.js";

// Sign in, create account, confirm email, reset password - one small state machine.
export default function AuthPage({ onSignedIn }) {
  const [mode, setMode] = useState("signin"); // signin | signup | confirm | forgot | reset
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);

  const run = (fn) => async (e) => {
    e.preventDefault();
    setErr("");
    setMsg("");
    setBusy(true);
    try {
      await fn();
    } catch (x) {
      if (x.type === "UserNotConfirmedException") setMode("confirm");
      setErr(x.message);
    } finally {
      setBusy(false);
    }
  };

  const signIn = run(async () => {
    await auth.signIn(email, password);
    onSignedIn();
  });
  const signUp = run(async () => {
    await auth.signUp(email, password);
    setMode("confirm");
    setMsg(`We emailed a 6-digit code to ${email}.`);
  });
  const confirm = run(async () => {
    await auth.confirm(email, code);
    if (password) {
      await auth.signIn(email, password);
      onSignedIn();
    } else {
      setMode("signin");
      setMsg("Email confirmed - please sign in.");
    }
  });
  const forgot = run(async () => {
    await auth.forgot(email);
    setMode("reset");
    setMsg(`If ${email} has an account, a reset code is on its way.`);
  });
  const reset = run(async () => {
    await auth.reset(email, code, password);
    await auth.signIn(email, password);
    onSignedIn();
  });

  const titles = {
    signin: "Welcome back",
    signup: "Create your account",
    confirm: "Check your email",
    forgot: "Reset your password",
    reset: "Choose a new password",
  };
  const submit = { signin: signIn, signup: signUp, confirm, forgot, reset }[mode];

  return (
    <div className="auth-wrap">
      <section className="auth-hero">
        <h1>🌿 Phy<span>Tro</span></h1>
        <p className="etym"><i>physikē trophē</i> · Greek for “natural nourishment”</p>
        <p className="lede">Know what's really in your cart before you get to the store.</p>
        <ul className="hero-points">
          <li>🔍 Search any product by name, brand or barcode</li>
          <li>🏬 Browse Walmart, Target &amp; more by aisle - healthiest picks first</li>
          <li>🔬 Three AI agents read the label, check FDA / EU / Prop 65 rules, and audit each other</li>
          <li>🔁 Get cleaner swaps that fit your allergies and diet</li>
          <li>📝 Build your list at home, check it off in the store</li>
        </ul>
      </section>
      <form className="card auth-card" onSubmit={submit}>
        <h2>{titles[mode]}</h2>
        {msg && <p className="ok">{msg}</p>}
        {err && <p className="err">{err}</p>}
        <label>Email
          <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        {(mode === "confirm" || mode === "reset") && (
          <label>Verification code
            <input inputMode="numeric" required value={code} onChange={(e) => setCode(e.target.value.trim())} />
          </label>
        )}
        {(mode === "signin" || mode === "signup" || mode === "reset") && (
          <label>{mode === "reset" ? "New password" : "Password"}
            <input type="password" required minLength={8}
                   autoComplete={mode === "signin" ? "current-password" : "new-password"}
                   value={password} onChange={(e) => setPassword(e.target.value)} />
            {mode !== "signin" && <small>8+ characters, with upper-case, lower-case and a number.</small>}
          </label>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "Please wait…" : { signin: "Sign in", signup: "Create account", confirm: "Confirm email",
                                    forgot: "Send reset code", reset: "Save & sign in" }[mode]}
        </button>
        <div className="auth-links">
          {mode === "signin" && <>
            <button type="button" className="link" onClick={() => setMode("signup")}>New here? Create an account</button>
            <button type="button" className="link" onClick={() => setMode("forgot")}>Forgot password?</button>
          </>}
          {mode === "confirm" && (
            <button type="button" className="link" onClick={run(async () => { await auth.resend(email); setMsg("New code sent."); })}>
              Resend code
            </button>
          )}
          {mode !== "signin" && <button type="button" className="link" onClick={() => setMode("signin")}>Back to sign in</button>}
        </div>
      </form>
    </div>
  );
}
