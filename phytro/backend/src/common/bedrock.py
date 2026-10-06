"""Thin agent runtime on the Bedrock Converse API (works with any tool-capable model).

run_agent() loops: model -> (toolUse -> run Python tool -> toolResult) -> model ...
until the model answers without asking for a tool. Every thought, tool call and
tool result is reported through `on_step` so the UI can show live
"Thinking / Action" states, and every call logs token usage + estimated cost
as one JSON line that the CloudWatch dashboard queries (observability).
"""
import json
import time

import boto3

from common import config

_client = None


def client():
    global _client
    if _client is None:
        _client = boto3.client("bedrock-runtime")
    return _client


def log_metric(**fields):
    """Structured log line -> CloudWatch Logs Insights (no custom-metric charges)."""
    print(json.dumps({"metric": "agent_call", **fields}))


def _cost(tokens_in, tokens_out):
    return round(tokens_in / 1e6 * config.PRICE_IN_PER_M + tokens_out / 1e6 * config.PRICE_OUT_PER_M, 6)


def run_agent(name, system_prompt, user_text, tools=None, on_step=None, max_turns=6, job_id=None):
    """Run one specialized agent. `tools` = {tool_name: (json_schema_spec, python_fn)}."""
    tools = tools or {}
    on_step = on_step or (lambda step: None)
    messages = [{"role": "user", "content": [{"text": user_text}]}]
    kwargs = {
        "modelId": config.MODEL_ID,
        "system": [{"text": system_prompt}],
        "inferenceConfig": {"maxTokens": 1500, "temperature": 0},
    }
    if tools:
        kwargs["toolConfig"] = {"tools": [{"toolSpec": spec} for spec, _ in tools.values()]}

    total_in = total_out = 0
    started = time.time()
    for turn in range(max_turns):
        resp = client().converse(messages=messages, **kwargs)
        usage = resp.get("usage", {})
        total_in += usage.get("inputTokens", 0)
        total_out += usage.get("outputTokens", 0)
        msg = resp["output"]["message"]
        messages.append(msg)

        tool_uses = [c["toolUse"] for c in msg["content"] if "toolUse" in c]
        thought = " ".join(c["text"] for c in msg["content"] if "text" in c).strip()
        if not tool_uses:
            break
        if thought:
            on_step({"agent": name, "kind": "thinking", "text": thought[:600]})

        results = []
        for tu in tool_uses:
            on_step({"agent": name, "kind": "action", "tool": tu["name"], "input": tu.get("input", {})})
            fn = tools.get(tu["name"], (None, None))[1]
            try:
                if fn is None:
                    raise ValueError(f"unknown tool {tu['name']}")
                out = fn(**(tu.get("input") or {}))
                status = "success"
            except Exception as exc:  # tool errors go back to the model, not up the stack
                out, status = {"error": str(exc)}, "error"
            on_step({"agent": name, "kind": "observation", "tool": tu["name"], "status": status,
                     "summary": _summarize(out)})
            results.append({"toolResult": {"toolUseId": tu["toolUseId"], "status": status,
                                           "content": [{"json": out if isinstance(out, dict) else {"result": out}}]}})
        messages.append({"role": "user", "content": results})
    else:
        thought = thought or "Stopped: too many tool turns."

    latency = round(time.time() - started, 2)
    log_metric(agent=name, job_id=job_id, model=config.MODEL_ID, turns=turn + 1, tokens_in=total_in,
               tokens_out=total_out, latency_s=latency, cost_usd=_cost(total_in, total_out))
    return {"text": thought, "tokens_in": total_in, "tokens_out": total_out, "latency_s": latency,
            "cost_usd": _cost(total_in, total_out)}


def _summarize(out):
    s = json.dumps(out, default=str)
    return s if len(s) <= 300 else s[:297] + "..."


def parse_json(text):
    """Pull the first JSON object out of a model reply (models sometimes wrap it in prose/fences)."""
    start, depth = text.find("{"), 0
    if start < 0:
        raise ValueError("no JSON object in agent reply")
    in_str = esc = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("unterminated JSON object in agent reply")


def apply_guardrail(text, source="OUTPUT"):
    """Bedrock Guardrails check. Returns (text_to_use, intervened: bool). No-op if not configured."""
    if not config.GUARDRAIL_ID:
        return text, False
    resp = client().apply_guardrail(guardrailIdentifier=config.GUARDRAIL_ID,
                                    guardrailVersion=config.GUARDRAIL_VERSION, source=source,
                                    content=[{"text": {"text": text}}])
    if resp.get("action") == "GUARDRAIL_INTERVENED":
        outs = resp.get("outputs") or [{"text": "Blocked by PhyTro safety policy."}]
        return outs[0]["text"], True
    return text, False
