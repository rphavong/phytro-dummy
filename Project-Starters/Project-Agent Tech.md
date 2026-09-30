### Op212

## Technical Scope and Delivery

## Agent 1 - Technical Delivery

Core function: ingest raw logs and return a structured incident summary.
The minimum deliverables:
- Log input handler
  - read .txt or .log
  - accept either a local test file or uploaded text from the GUI
- Agent 1 system prompt
  - defines the Log Analyst role
  - tells it what fields to extract
  - tells it to ignore noise
  - tells it not to recommend remediation
- Bedrock invocation code
  - send logs + prompt to Bedrock
  - receive response
  - parse structured output
- Structured response schema
  - ideally JSON
  - consistent keys every time
Example:
```json{
  "service": "payment-api",
  "issue": "memory exhaustion",
  "severity": "high",
  "evidence": [
    "memory usage exceeded 90%",
    "request timeout errors increased",
    "health checks failed"
  ],
  "confidence": 0.91
}
```
- Validation / parsing
  - make sure required fields exist
  - fail cleanly if Bedrock returns malformed output
- Sample log datasets
  - at least 2–3 log files for Agent 1 testing
  - one should be noisy
  - one should represent a clear failure
  - one can represent “no meaningful incident”
- Unit tests
  - log loader test
  - output schema test
  - no-incident case
  - malformed-response handling
- Integration contract
  - document exactly what Agent 2 receives
That contract is important because it prevents both of you from building against different assumptions.
# Agent 1 - Repo Structure
```
project-root/
│
├── agents/
│   ├── __init__.py
│   └── log_analyst.py
│
├── prompts/
│   └── log_analyst_prompt.txt
│
├── schemas/
│   └── incident_schema.py
│
├── data/
│   └── logs/
│       ├── normal.log
│       ├── memory_failure.log
│       └── noisy_incident.log
│
├── tests/
│   ├── test_log_loader.py
│   └── test_log_analyst.py
│
├── utils/
│   └── log_loader.py
│
└── README.md
```

## Agent 2 - Technical Delivery
Agent 2 — Technical Deliverables
- Input contract
  - accept Agent 1’s structured JSON
  - use fields like service, issue, severity, evidence
- Knowledge Base data set
  - 5+ docs overall for the project
  - Agent 2 owns the runbook-style docs
  - include at least one old/current conflict
Example:
- runbook_memory_v1.md
- runbook_memory_v2.md
- network_runbook.md
- known_issues.md
- architecture_overview.md

- S3 upload path
  - store source docs in S3
  - keep the folder structure predictable
- Bedrock Knowledge Base connection
  - retrieve relevant chunks based on Agent 1’s incident summary
- Agent 2 system prompt
  - only interpret documentation
  - do not re-diagnose the logs
  - do not execute actions
  - identify conflicts and outdated guidance
- Retrieval/query builder
  - turn Agent 1 JSON into a good search request
Example:
```text
    Find the current remediation guidance for:
    service: payment-api
    issue: memory exhaustion
    severity: high
```
- Structured output
  - consistent JSON back to Agent 3
Example:
```json
{
  "recommended_action": "scale_service",
  "steps": [
    "increase replicas",
    "monitor memory",
    "restart unhealthy instance if needed"
  ],
  "conflict_detected": true,
  "conflict_note": "v1 recommends restart first; v2 requires scaling first",
  "source": "runbook_memory_v2.md",
  "confidence": 0.88
}
```
- Conflict-handling test
  - prove Agent 2 notices old vs current docs
- No-match test
  - if nothing relevant is found, return something like:
```json
{
  "recommended_action": "escalate",
  "reason": "No trusted remediation guidance found"
}
```
# Agent 2 - Repo Structure
```
project-root/
│
├── agents/
│   ├── log_analyst.py
│   └── runbook_investigator.py
│
├── prompts/
│   ├── log_analyst_prompt.txt
│   └── runbook_investigator_prompt.txt
│
├── schemas/
│   ├── incident_schema.py
│   └── recommendation_schema.py
│
├── knowledge/
│   ├── runbook_memory_v1.md
│   ├── runbook_memory_v2.md
│   ├── network_runbook.md
│   ├── known_issues.md
│   └── architecture_overview.md
│
├── utils/
│   └── kb_retriever.py
│
├── tests/
│   ├── test_runbook_investigator.py
│   └── test_kb_retrieval.py
│
└── README.md
```
## Agent 3 - Technical Delivery
- Input contract
  - accept Agent 1 JSON
  - accept Agent 2 JSON
  - combine both into one decision context
Example inputs:
```json
{
  "service": "payment-api",
  "issue": "memory exhaustion",
  "severity": "high",
  "confidence": 0.91
}
```
```json
{
  "recommended_action": "scale_service",
  "conflict_detected": false,
  "source": "runbook_memory_v2.md",
  "confidence": 0.88
}
```
- Agent 3 system prompt
  - evaluate the diagnosis and recommendation
  - decide whether action is justified
  - do not invent new remediation steps
  - escalate when confidence is low or docs conflict
- Decision rules
  - simple and explicit
  - example:
```text
If incident confidence >= 0.80
AND runbook confidence >= 0.80
AND no unresolved conflict exists
THEN action may proceed
```
Otherwise:
escalate for human review

- Structured decision output
  - return consistent JSON
Example:
```json
{
  "decision": "act",
  "action": "create_incident",
  "reason": "High-confidence incident with verified remediation guidance",
  "requires_human_review": false
}
```
Or:
```json
{
  "decision": "escalate",
  "action": "notify_operator",
  "reason": "Conflicting runbook guidance detected",
  "requires_human_review": true
}
```

- Action tool / Lambda
  - Agent 3 is the only agent allowed to call it
  - simplest tool:
create_incident(    service,    issue,    severity,    recommended_action)


- Action result
  - Lambda returns a record
```json
{
  "incident_id": "INC-1042",
  "status": "created"
}
```
- Safety / fallback behavior
  - if inputs are incomplete
  - if confidence is too low
  - if Agent 2 found conflicting guidance
  - if Lambda fails
Then Agent 3 should fall back to:
>human review required

# Agent 3 - Repo Structure
```
project-root/
│
├── agents/
│   ├── log_analyst.py
│   ├── runbook_investigator.py
│   └── response_coordinator.py
│
├── prompts/
│   ├── log_analyst_prompt.txt
│   ├── runbook_investigator_prompt.txt
│   └── response_coordinator_prompt.txt
│
├── schemas/
│   ├── incident_schema.py
│   ├── recommendation_schema.py
│   └── decision_schema.py
│
├── actions/
│   └── create_incident.py
│
├── utils/
│   └── lambda_client.py
│
├── tests/
│   ├── test_response_coordinator.py
│   └── test_create_incident.py
│
└── README.md

```
