import { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Navigate, NavLink, Route, Routes, useLocation, useNavigate } from "react-router-dom";
import { api, auth, loadConfig } from "./api.js";
import AuthPage from "./pages/AuthPage.jsx";
import ShopPage from "./pages/ShopPage.jsx";
import ProductPage from "./pages/ProductPage.jsx";
import ListPage from "./pages/ListPage.jsx";
import ProfilePage from "./pages/ProfilePage.jsx";
import SearchBox from "./components/SearchBox.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import { AppCtx } from "./ctx.js";
import "./styles.css";


function Shell() {
  const [user, setUser] = useState(auth.user());
  const [meta, setMeta] = useState(null);
  const [profile, setProfile] = useState(null);
  const [listCount, setListCount] = useState(0);
  const [error, setError] = useState("");
  const navigate = useNavigate();
  const { pathname } = useLocation();

  useEffect(() => {
    if (!user) return;
    Promise.all([api.meta(), api.profile(), api.list()])
      .then(([m, p, l]) => {
        setMeta(m);
        setProfile(p);
        setListCount(l.items.length);
        const firstVisit = !p.allergens.length && !p.avoid.length && !p.display_name;
        if (firstVisit && !sessionStorage.getItem("phytro.onboarded")) {
          sessionStorage.setItem("phytro.onboarded", "1");
          navigate("/profile?welcome=1");
        }
      })
      .catch((e) => setError(e.message));
  }, [user]);

  if (!user) return <AuthPage onSignedIn={() => setUser(auth.user())} />;
  if (error) return <div className="center-msg">⚠️ {error}</div>;
  if (!meta || !profile) return <div className="center-msg"><span className="spinner" /> Loading PhyTro…</div>;

  const signOut = () => {
    auth.signOut();
    setUser(null);
    navigate("/");
  };

  return (
    <AppCtx.Provider value={{ meta, profile, setProfile, listCount, setListCount }}>
      <header className="topbar">
        <NavLink to="/" className="brand">🌿 Phy<span>Tro</span></NavLink>
        <nav>
          <NavLink to="/" end>Shop</NavLink>
          <NavLink to="/list">My list{listCount > 0 && <b className="pill">{listCount}</b>}</NavLink>
          <NavLink to="/profile">Profile</NavLink>
        </nav>
        {pathname !== "/search" && <SearchBox />}
        <button className="ghost small" onClick={signOut} title={user.email}>Sign out</button>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<ShopPage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/product/:barcode" element={<ProductPage />} />
          <Route path="/list" element={<ListPage />} />
          <Route path="/profile" element={<ProfilePage />} />
          <Route path="*" element={<Navigate to="/" />} />
        </Routes>
      </main>
      <footer className="foot">
        PhyTro is decision support, not medical advice. Product data:{" "}
        <a href="https://world.openfoodfacts.org" target="_blank" rel="noreferrer">Open Food Facts</a> (ODbL).
      </footer>
    </AppCtx.Provider>
  );
}

function Boot() {
  const [ready, setReady] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    loadConfig().then(() => setReady(true)).catch((e) => setErr(e.message));
  }, []);
  if (err) return <div className="center-msg">⚠️ {err}</div>;
  if (!ready) return <div className="center-msg"><span className="spinner" /></div>;
  return (
    <BrowserRouter>
      <Shell />
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")).render(<Boot />);
