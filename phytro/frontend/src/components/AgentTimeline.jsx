// Live view of the 3-agent run: each agent's lane shows Waiting / Thinking / Acting / Done.
const AGENTS = [
  { name: "Label Scout", icon: "🔎", job: "Reads the raw label and pulls out the real ingredients" },
  { name: "Toxicology Analyst", icon: "🧪", job: "Checks each ingredient against FDA, EU and Prop 65 documents" },
  { name: "Shopper Advocate", icon: "🛡️", job: "Audits the analysis, applies your profile, finds better swaps" },
];
const KIND_ICON = { start: "▶️", thinking: "💭", action: "🔧", observation: "📥", guardrail: "🚧", handoff: "➡️", done: "✅", error: "❌" };
const TOOL_LABEL = {
  lookup_product: "Looking up product",
  search_regulations: "Searching regulations",
  find_alternatives: "Finding healthier options",
  add_to_shopping_list: "Adding to your list",
};

function laneState(steps, idx, jobStatus) {
  const mine = steps.filter((s) => s.agent === AGENTS[idx].name);
  if (!mine.length) return jobStatus === "error" ? "skipped" : "waiting";
  const last = mine[mine.length - 1];
  if (last.kind === "handoff" || last.kind === "done") return "done";
  if (jobStatus === "error") return "error";
  if (last.kind === "action") return "acting";
  return "thinking";
}

const STATE_TEXT = { waiting: "Waiting", thinking: "Thinking…", acting: "Taking action…", done: "Done", error: "Stopped", skipped: "Skipped" };

export default function AgentTimeline({ steps = [], status }) {
  return (
    <div className="agents">
      {AGENTS.map((a, i) => {
        const state = laneState(steps, i, status);
        const mine = steps.filter((s) => s.agent === a.name);
        return (
          <div key={a.name} className={`agent-lane ${state}`}>
            <div className="agent-head">
              <span className="agent-icon">{a.icon}</span>
              <div className="grow">
                <strong>{i + 1}. {a.name}</strong>
                <div className="muted small-text">{a.job}</div>
              </div>
              <span className={`state ${state}`}>
                {(state === "thinking" || state === "acting") && <span className="spinner tiny" />} {STATE_TEXT[state]}
              </span>
            </div>
            {mine.length > 0 && (
              <ol className="steps">
                {mine.map((s, j) => (
                  <li key={j} className={`step ${s.kind}`}>
                    <span>{KIND_ICON[s.kind] || "•"}</span>
                    <span className="grow">
                      {s.kind === "action" && <><b>{TOOL_LABEL[s.tool] || s.tool}</b>{s.input?.query ? `: “${s.input.query}”` : ""}{s.input?.barcode ? ` ${s.input.barcode}` : ""}</>}
                      {s.kind === "observation" && <span className="muted">{s.status === "error" ? "Tool error: " : "Got result: "}{s.summary?.slice(0, 140)}</span>}
                      {s.kind !== "action" && s.kind !== "observation" && s.text}
                    </span>
                  </li>
                ))}
              </ol>
            )}
          </div>
        );
      })}
      {steps.some((s) => s.agent === "System") && (
        <p className="err">❌ {steps.find((s) => s.agent === "System").text}</p>
      )}
    </div>
  );
}
