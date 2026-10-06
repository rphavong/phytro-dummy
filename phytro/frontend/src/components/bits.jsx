// Small shared UI pieces.
export function ScoreBadge({ score, grade, size = "md", label }) {
  const tone = grade === "Great" ? "great" : grade === "Good" ? "good" : grade === "Fair" ? "fair" : "poor";
  return (
    <div className={`score ${tone} ${size}`} title={`PhyTro score ${score}/100 - ${grade}`}>
      <strong>{score}</strong>
      <span>{label || grade}</span>
    </div>
  );
}

export function Level({ level }) {
  const icon = { high: "⛔", moderate: "⚠️", low: "ℹ️", none: "✅" }[level] || "•";
  return <span className={`level ${level}`}>{icon} {level}</span>;
}

export function ProductThumb({ src, alt }) {
  return src ? <img className="thumb" src={src} alt={alt} loading="lazy" /> : <div className="thumb empty">🛍️</div>;
}

export function Empty({ icon, title, children }) {
  return (
    <div className="empty-state">
      <div className="big">{icon}</div>
      <h3>{title}</h3>
      <div>{children}</div>
    </div>
  );
}
