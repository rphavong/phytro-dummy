## Start for Op212

## Track 2: The "Entropy" Sector (Infrastructure & Systems)

# Infrastructure
```
AWS Bedrock
Bedrock Knowledge Base / RAG
Lambda
Streamlit
Terraform
GitHub Actions
```
## Agent 1 — Log Analyst
```
Job: Find the problem.
It receives the raw noisy logs and outputs only the important signals: affected service, suspected issue, severity, evidence, and confidence.
Example: “API service showing increasing memory usage, repeated timeout errors, and failed health checks. Suspected memory exhaustion. Severity: High.”
```
take messy logs → identify meaningful failure signals → return a structured incident summary
The building blocks are:
>1. Input
   - raw .txt / .log
   - maybe uploaded through Streamlit
   - could also use a fixed test log file for demo
>2. Pre-processing
   - basic Python reads the file
   - optionally trims empty lines / timestamps / obvious noise
   - no fancy ML needed
>3. Bedrock model call
   - send the relevant log content to Bedrock
   - system prompt tells the agent exactly what to extract
   - this is the actual “Agent 1”
>4. Structured output
   I’d force something like:
```json
{
  "service": "payment-api",
  "issue": "memory exhaustion",
  "severity": "high",
  "evidence": [
    "memory usage exceeded 90%",
    "repeated request timeouts",
    "health checks failing"
  ],
  "confidence": 0.91
}
```

>5. Handoff
   - that JSON becomes the input to Agent 2
   - Agent 2 never needs the whole raw log unless we decide later that it does

## Agent 2 — Runbook Investigator
```
Job: Figure out what the documentation says to do.
It takes Agent 1’s diagnosis and searches the Bedrock Knowledge Base containing runbooks, known issues, architecture docs, and old/current procedures. This is also where we demonstrate conflicting-document handling.
Example: “Current runbook says scale replicas before restart. Older runbook recommends immediate restart; newer guidance supersedes it.”
```
Take Agent 1’s incident summary → search trusted documentation → return the recommended response

>1. Input
Agent 2 does not read the raw logs first.
It receives the structured result from Agent 1:
```json
{
  "service": "payment-api",
  "issue": "memory exhaustion",
  "severity": "high",
  "evidence": [
    "memory usage exceeded 90%",
    "request timeouts",
    "health checks failing"
  ],
  "confidence": 0.91
}
```
That keeps the handoff clean.

>2. Knowledge Source
This is where the Bedrock Knowledge Base / RAG comes in.
Agent 2 searches documents like:
- runbook_memory.md
- runbook_network.md
- known_issues.md
- architecture.md
- old_runbook.md

The documents live in S3 and get indexed into the Knowledge Base.

>3. Retrieval
Agent 2 uses the issue from Agent 1 to ask something like:
Find the current remediation procedure for:

Service: payment-api
Issue: memory exhaustion
Severity: high

The Knowledge Base returns relevant chunks.

>4. Bedrock reasoning
Then Agent 2 reviews the retrieved documentation and answers:
- what procedure applies
- what steps are recommended
- whether documents conflict
- which source appears current
- whether the issue requires escalation
Example output:
```json
{
  "recommended_action": "scale_service",
  "steps": [
    "increase replicas from 2 to 4",
    "monitor memory utilization",
    "restart unhealthy instance only if memory remains above threshold"
  ],
  "conflict_detected": true,
  "conflict_note": "Older runbook recommends immediate restart. Current runbook requires scaling first.",
  "source": "runbook_memory_v2.md"
}
```

>5. Handoff to Agent 3
Agent 3 then receives both:
```
Agent 1:
What is wrong?

Agent 2:
What does the documentation say to do?
```

## Agent 3 — Response Coordinator
```
Job: Make the final operational decision.
It receives the diagnosis + runbook recommendation and decides whether an action is warranted. It is the only agent with a tool/action.
```
take Agent 1’s diagnosis + Agent 2’s runbook recommendation → decide whether to act → call the tool

>1. Input
Agent 3 receives both structured outputs.
From Agent 1:
```json
{
  "service": "payment-api",
  "issue": "memory exhaustion",
  "severity": "high",
  "confidence": 0.91
}
```

>From Agent 2:
```json
{
  "recommended_action": "scale_service",
  "conflict_detected": true,
  "source": "runbook_memory_v2.md"
}
```

>2. Decision Logic
Agent 3 checks things like:
- Is the confidence high enough?
- Is the severity serious enough?
- Did Agent 2 find a valid/current runbook?
- Was there a documentation conflict?
- Is the requested action safe to automate?
For the MVP, keep this simple.
Example rule:
```
If:
confidence >= 0.80
AND severity = high
AND current runbook found

Then:
create incident
```

>3. Bedrock Reasoning
Agent 3 produces a final decision like:
```json
{
  "decision": "act",
  "action": "create_incident",
  "reason": "High-confidence memory exhaustion event with matching current runbook",
  "requires_human_review": false
}
```
Or:
```json
{
  "decision": "escalate",
  "action": "notify_operator",
  "reason": "Conflicting runbooks and insufficient confidence",
  "requires_human_review": true
}
```

>4. Tool / Action
This is the agent that actually gets the tool.
For the MVP, I’d keep the tool extremely simple:
create_incident(    service,    issue,    severity,    recommended_action)


The Lambda can just write the incident to:
DynamoDB
or
JSON file / S3

No real infrastructure changes needed.

>5. Final Output
Something like:
```json
{
  "incident_id": "INC-1042",
  "status": "created",
  "service": "payment-api",
  "severity": "high",
  "recommended_action": "scale_service"
}
```
