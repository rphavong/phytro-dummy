import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

// One box for everything: type a product name / brand / description ("cheerios", "oat milk unsweetened")
// or a barcode (all digits) - or scan a barcode with the phone camera when the browser supports it.
export default function SearchBox({ big = false, autoFocus = false }) {
  const [params] = useSearchParams();
  const [text, setText] = useState(params.get("q") || "");
  const [scanning, setScanning] = useState(false);
  const video = useRef(null);
  const navigate = useNavigate();
  const canScan = typeof window !== "undefined" && "BarcodeDetector" in window;

  useEffect(() => { setText(params.get("q") || ""); }, [params]);

  const go = (raw) => {
    const value = String(raw).trim();
    const digits = value.replace(/[\s-]/g, "");
    if (/^\d{6,14}$/.test(digits)) navigate(`/product/${digits}`);       // looks like a barcode
    else if (value.length >= 2) navigate(`/search?q=${encodeURIComponent(value)}`);
  };

  const scan = async () => {
    setScanning(true);
    let stream;
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
      video.current.srcObject = stream;
      await video.current.play();
      const detector = new window.BarcodeDetector({ formats: ["ean_13", "ean_8", "upc_a", "upc_e"] });
      for (let i = 0; i < 150; i++) {
        const found = await detector.detect(video.current);
        if (found.length) { go(found[0].rawValue); break; }
        await new Promise((r) => setTimeout(r, 200));
      }
    } catch (e) {
      alert("Camera not available: " + e.message);
    } finally {
      stream?.getTracks().forEach((t) => t.stop());
      setScanning(false);
    }
  };

  return (
    <form className={big ? "searchbox big" : "searchbox"} role="search" onSubmit={(e) => { e.preventDefault(); go(text); }}>
      <span className="search-icon" aria-hidden>🔍</span>
      <input type="search" value={text} onChange={(e) => setText(e.target.value)} autoFocus={autoFocus}
             placeholder={big ? "Search any product, brand or ingredient — or type a barcode" : "Search products or barcode…"}
             aria-label="Search products by name, brand, description or barcode" enterKeyHint="search" />
      {big && <button className="primary">Search</button>}
      {canScan && <button type="button" className="ghost small scan" onClick={scan} title="Scan a barcode">📷</button>}
      {canScan && (
        <div className={scanning ? "scanner" : "scanner hidden"}>
          <video ref={video} playsInline muted />
          <p>Point the camera at the barcode…</p>
        </div>
      )}
    </form>
  );
}
