# 🌿 PhyTro — natural nourishment, decoded

**PhyTro** (from the Greek *physikē trophē*, "natural nourishment") helps shoppers pick the healthiest product
before they reach the store. You can:
- search any product by name, brand, description or barcode;
- browse Walmart, Target and other stores aisle by aisle, healthiest first;
- run a **three-agent AI analysis** on AWS Bedrock that reads the label, checks every ingredient against
  FDA / EU / California Prop 65 documents, audits its own findings, and suggests (or adds) a cleaner swap to
  your shopping list.

Every account's profile, list and reports are private and saved.

> AICO Mini-Capstone "Redemption Week": Multi-Agent Bedrock requirement plus four "Pick Three" items:
> IaC (Terraform) · Automated CI/CD (GitHub Actions) · Security & Governance (Guardrails + least-privilege IAM) ·
> Observability (CloudWatch dashboard for agent performance & cost). Web GUI with live Thinking/Action states.

**Contents:**
[1 Folders](#1-the-two-folders-you-need-to-know) ·
[2 Install](#2-install-tools-once-per-computer) ·
[3 Get the code](#3-get-the-code) ·
[4 First run](#4-first-run-deploy-your-own-copy-step-by-step) ·
[5 Everyday commands](#5-everyday-commands) ·
[6 Git & GitHub Actions](#6-git-github-actions--how-teammates-push-test-and-deploy) ·
[7 Migrating from SafeCart](#7-one-time-migrating-an-existing-safecart-deployment-robby-only) ·
[8 Troubleshooting](#8-troubleshooting) ·
[9 Architecture](#9-architecture) ·
[10 Requirement map](#10-requirement-map-for-graders)

---

## 1. The two folders you need to know

```
mini-capstone/               ← REPO ROOT  (git commands, GitHub workflows live here)
├── .github/workflows/       ← ci.yml + deploy.yml (GitHub only reads workflows at the repo root)
└── phytro/                  ← APP FOLDER (run every  make / terraform / python  command here)
    ├── Makefile             ← type  make  to list all commands
    ├── backend/  frontend/  infra/  knowledge/  scripts/  docs/
```

**Rule of thumb:** `git` commands run in the **repo root**, everything else runs in **`phytro/`**.
Your terminal prompt shows where you are: `… mini-capstone %` is the repo root, `… phytro %` is the app folder.
Errors like `No rule to make target` or `No such file or directory: scripts/...` almost always mean you're in the
wrong folder. Run `pwd`, then `cd` to the right one.

## 2. Install tools (once per computer)

| Tool | Check | Install (macOS) |
|---|---|---|
| Python 3.11+ | `python3 --version` | `brew install python@3.12` |
| Node 22+ | `node --version` | `brew install node` |
| Terraform ≥ 1.10 | `terraform -version` | `brew tap hashicorp/tap && brew install hashicorp/tap/terraform` |
| AWS CLI v2 | `aws --version` | `brew install awscli` |
| Git + GitHub access | `git --version` | `brew install git` |

AWS credentials for the Code Platoon account (each person uses their own IAM user):
```bash
aws configure                    # access key, secret key, region us-east-1, output json
aws sts get-caller-identity      # must print the Code Platoon account id - not an error
```

## 3. Get the code

**Option A — clone the team repo (lab partners, recommended):**
```bash
cd ~/Documents                                   # any parent folder you like
git clone https://github.com/<org-or-user>/<team-repo>.git mini-capstone
cd mini-capstone                                 # ← repo root
git checkout -b <your-name>-dev                  # work on your own branch (see §6)
cd phytro                                        # ← app folder
```

**Option B — from a zip file** (e.g. `phytro.zip` sent in chat). Click the file's download button first: it only
exists on your Mac once downloaded (usually to `~/Downloads`).
```bash
cd ~/Documents/aico-echo/challenges/week24/mini-capstone   # ← repo root: the folder that should CONTAIN phytro/
unzip -o ~/Downloads/phytro.zip                            # creates/updates  .github/  and  phytro/
ls                                                          # you should see: phytro   (and .github with ls -a)
cd phytro                                                   # ← app folder
```
If Safari auto-unzipped it into a folder instead, copy that folder's contents:
`cp -R ~/Downloads/phytro/. .` (run from the repo root).

## 4. First run: deploy your own copy, step by step

Everything below runs in **`phytro/`** unless a step says otherwise.

**4.1 Set up the local environment and run the tests** (about 1 minute):
```bash
make setup                       # creates .venv/ and installs frontend packages
source .venv/bin/activate        # prompt now starts with (.venv); repeat in every new terminal
make test                        # expect: 16 passed
```

**4.2 Check that Bedrock can answer** (costs a fraction of a cent):
```bash
aws bedrock-runtime converse --region us-east-1 --model-id us.amazon.nova-lite-v1:0 \
  --messages '[{"role":"user","content":[{"text":"Say hi"}]}]' --query 'output.message.content[0].text'
```
- A greeting back means it works.
- `AccessDeniedException` means you need to enable **Amazon Nova Lite** in the Bedrock console
  (**Model access**), or ask the instructor for Bedrock permissions.

**4.3 Regulatory documents** (the AI's evidence library). *Skip this if you cloned the repo: the documents and
index are already committed.*
```bash
make knowledge                   # downloads 10 public documents, needs at least 5
```
Some government sites block scripts. For each failed document, the script prints a URL. Open it in Chrome, press
⌘S, save it into `knowledge/raw/` as `<id>.pdf` or `<id>.html` (the id is printed), then run `make knowledge` again.

**4.4 Terraform state bucket** (where Terraform remembers what it created). **Once per AWS account per person.**
- **If a teammate already deployed** and you want to work on *their* (shared) deployment, don't run this.
  Instead create `infra/backend.hcl` with the bucket name they give you:
  ```bash
  cat > infra/backend.hcl <<'EOF'
  bucket       = "PASTE-THE-TEAM-STATE-BUCKET-NAME"
  key          = "phytro/terraform.tfstate"
  region       = "us-east-1"
  use_lockfile = true
  encrypt      = true
  EOF
  ```
- **For your own separate copy** (your own URL, data and users, recommended while experimenting):
  ```bash
  export OWNER=yourname            # lowercase, no spaces. Keep it set in this terminal: every make command uses it
  make state                       # prints ✅ State bucket: phytro-yourname-tfstate-xxxxxx  and writes infra/backend.hcl
  ```

**4.5 Create the AWS resources** (about 5 minutes; CloudFront is the slow part):
```bash
make infra                       # shows the plan, then asks for 'yes'
```
Read the summary line before typing `yes`. A brand-new copy shows `Plan: 39 to add, 0 to change, 0 to destroy`.
**Never type yes if it says "to destroy" and you didn't expect it.** Ask the team first.

**4.6 Publish the website, then load product data:**
```bash
make web                         # prints  Open: https://xxxx.cloudfront.net   (wait ~1 minute)
make seed                        # ~20 min: pre-loads every store x aisle; safe to stop with Ctrl-C and resume later
make seed-missing                # later: retries only aisles that failed (Open Food Facts often returns 503)
```

**4.7 Try it:** open the URL and create an account. The 6-digit code comes from `no-reply@verificationemail.com`,
so check spam. Fill in your profile, search for `coffee`, open a product and click **Run AI analysis**.
The full walkthrough is in [docs/USER_GUIDE.md](docs/USER_GUIDE.md).

**4.8 Quick health check** at any time:
```bash
API=$(terraform -chdir=infra output -raw api_url)
curl -s $API/health                                     # {"ok": true}
curl -s -o /dev/null -w '%{http_code}\n' $API/profile   # 401 = private routes are locked (correct)
```

## 5. Everyday commands

Run these in **`phytro/`** with `(.venv)` active. Type `make` to list them all.

| Command | What it does |
|---|---|
| `make test` | Unit tests, no AWS needed. Run before every push. |
| `make infra` | Apply Terraform changes (after editing `infra/` or `backend/`). |
| `make web` | Rebuild and publish the website (after editing `frontend/`). |
| `make dev` | Run the website locally at http://localhost:5173 against the deployed API. |
| `make outputs` | App URL, API URL, table name, dashboard link. |
| `make logs` | Last 15 min of the AI agent worker logs. |
| `make seed-missing` | Fill aisles that are empty. |
| `make backup` / `make restore` | Save or restore seeded aisles to/from `catalog-backup.json`. |
| `make destroy` | Delete this deployment from AWS (end of course). |

If you chose your own `OWNER` in 4.4, run `export OWNER=yourname` in each new terminal before using `make`.

## 6. Git & GitHub Actions — how teammates push, test and deploy

### How the pipeline works
| You do | GitHub runs | Needs AWS? |
|---|---|---|
| Push any branch except `main`, or open a pull request | **CI** (`ci.yml`): backend tests, `terraform fmt` + `validate`, website build | No |
| Merge into `main` (or click **Run workflow** on Deploy) | **CI** first, then **Deploy** (`deploy.yml`): `terraform apply` → publish website → smoke test | Yes (repo secrets) |

Deploy updates the **team's shared deployment** (the `OWNER` repository variable, default `robby`) using the shared
state bucket. Two applies can't collide because Terraform locks the state.

### One-time repo setup (repo admin does this once)
1. **Settings → Collaborators** → add each teammate (so they can push branches).
2. **Actions tab** → if the repo is a fork, click *"I understand my workflows, go ahead and enable them"*.
3. **Settings → Secrets and variables → Actions → New repository secret**:

   | Secret | Value |
   |---|---|
   | `AWS_ACCESS_KEY_ID` | access key of an IAM user that can deploy to the Code Platoon account |
   | `AWS_SECRET_ACCESS_KEY` | its secret key |
   | `TF_STATE_BUCKET` | the team state bucket, e.g. `safecart-robby-tfstate-572075` (the old name is fine) |

   Optional, under the **Variables** tab: `OWNER` = the resource prefix to deploy (default `robby`).

### Your daily loop (teammate)
```bash
# repo root
cd ~/Documents/mini-capstone
git checkout main && git pull                       # start from the latest code
git checkout -b <your-name>/<short-topic>           # e.g. maria/search-filters

# app folder: make your change, then test it
cd phytro
make test                                           # must pass before you push
make dev                                            # optional: click through the site locally

# repo root: commit and push
cd ..
git status                                          # check what changed
git add phytro .github                              # stage only project files
git commit -m "Add healthiest-first sort to search"
git push -u origin <your-name>/<short-topic>
```
Then on GitHub:
1. Open the **Actions** tab. The **CI** run for your branch should show 3 green jobs
   (`backend-tests`, `terraform-validate`, `frontend-build`). Click a red job to read its log.
2. Click **Compare & pull request** → describe the change → **Create pull request**. CI runs again on the PR.
3. After review, **Merge**. This starts **Deploy**. Watch it in **Actions → Deploy**. When it finishes, the run
   summary shows `🚀 Deployed: https://…` and the live site has your change about 1 minute later.
4. Back on your Mac (repo root): `git checkout main && git pull`.

**Re-running:** open a failed run → **Re-run jobs**. **Deploying without a code change** (e.g. after fixing secrets):
**Actions → Deploy → Run workflow → main**.

### Common CI/CD failures
| Error in the log | Fix |
|---|---|
| `terraform fmt -check` failed | Run `terraform -chdir=infra fmt` in `phytro/`, commit, push |
| Tests fail in CI but pass locally | Run `make test` in `phytro/` and read the first failure; check the change is committed |
| `Credentials could not be loaded` | Repo secrets missing or misspelled (§6 one-time setup) |
| `Error acquiring the state lock` | Someone else is applying. Wait for their run; don't force-unlock |
| Deploy didn't start after merge | It only runs when files under `phytro/` or `.github/workflows/` changed; use **Run workflow** |

## 7. One-time: migrating an existing SafeCart deployment (Robby only)

The project was renamed from SafeCart to PhyTro (SafeCart is taken). AWS can't rename most resources, so
Terraform **replaces** them. The website and API addresses usually stay the same. User accounts start fresh,
and seeded aisles are backed up and restored.

```bash
deactivate 2>/dev/null                                  # leave the old venv
cd ~/Documents/aico-echo/challenges/week24/mini-capstone # ← repo root
mv safecart phytro                                       # keeps your docs, index, backend.hcl, .terraform
unzip -o ~/Downloads/phytro.zip                          # new code over the top (+ .github)
rm -f phytro/frontend/src/components/BarcodeBox.jsx      # replaced by SearchBox.jsx

cd phytro                                                # ← app folder from here on
rm -rf .venv && make setup && source .venv/bin/activate  # the venv must be rebuilt after a folder move
make test                                                # 16 passed

make backup TABLE=safecart-robby                         # ✅ saved … rows → catalog-backup.json

# move the Terraform state to the new key (same bucket)
sed -i '' 's#safecart/terraform.tfstate#phytro/terraform.tfstate#' infra/backend.hcl
terraform -chdir=infra init -migrate-state -backend-config=backend.hcl   # answer: yes

make infra        # plan replaces safecart-robby-* with phytro-robby-*: "N to add, M to change, N to destroy",
                  # and every destroy is a safecart-robby-* resource. Type yes (~5-8 min)
make restore      # ✅ restored … rows into phytro-robby
make web
make outputs      # app_url: open it and create your account again
```
Then commit the rename from the **repo root**:
```bash
cd .. && git add -A .github safecart phytro
git commit -m "Rename SafeCart -> PhyTro; add search by name"
git push
```
No GitHub secret changes are needed: the deploy workflow already points to `phytro/` and the same state bucket.

## 8. Troubleshooting

| Symptom | Cause → fix |
|---|---|
| `No rule to make target` / `No such file or directory` | Wrong folder: `cd` into `phytro/` (§1) |
| `zsh: command not found: python` / `pytest` | Venv not active: `source .venv/bin/activate` in `phytro/` |
| `make state` exits silently, `echo $?` → 141 | Old script; update the code (fixed: uses `openssl rand`) |
| `AccessDeniedException` on `CreateGuardrail` | Shared-account limit: `terraform -chdir=infra apply -var enable_guardrail=false` |
| `HTTP Error 503` while seeding/searching | Open Food Facts is overloaded; the app serves cached data. Run `make seed-missing` later |
| Aisle says "store not confirmed" | Open Food Facts has few items tagged for that store; similar US products fill in |
| Verification email missing | Check spam; Cognito's default sender allows ~50 emails/day |
| Site still shows the old version | CloudFront refresh takes about 1 minute; hard-reload (⌘⇧R) |
| AI analysis shows ❌ | `make logs` and read the last error |

## 9. Architecture

```
 Browser (React on CloudFront + private S3)
   │  sign up / sign in ──────────────► Amazon Cognito (email verification, JWT)
   │  HTTPS + JWT
   ▼
 API Gateway HTTP API ── JWT authorizer (every route but /health), 10 req/s throttle
   ▼
 Lambda "api"  ─── DynamoDB (single table, on-demand): profile · list · reports · jobs · aisle lists · caches
   │   ├── /search: stored aisle lists (instant, in-memory) + Open Food Facts full-text search (cached 24 h)
   │   └── /browse: seeded aisle lists, topped up with all-US products when a store has few tagged items
   │ async invoke (no 30 s API timeout)
   ▼
 Lambda "worker" — 3-agent pipeline (Bedrock Converse API, Amazon Nova Lite)
   ① Label Scout ───tool: lookup_product──► Open Food Facts   (label text screened by Guardrail INPUT)
   ② Toxicology Analyst ──tool: search_regulations──► BM25 index of raw regulatory documents
   ③ Shopper Advocate (audits ②) ──tools: find_alternatives, add_to_shopping_list──► DynamoDB
                                                         (final answer screened by Guardrail OUTPUT)
   each step → DynamoDB job record → UI polls every 1.5 s → live agent lanes
   each agent call → JSON log line → CloudWatch dashboard (tokens, latency, $ per agent)
```

| Agent | Responsibility (prompts in `backend/src/agents/prompts.py`) | Tools |
|---|---|---|
| **1. Label Scout** | Turn messy crowd-sourced label data into clean facts; ignore marketing/legal noise | `lookup_product` |
| **2. Toxicology Analyst** | Cite regulatory documents for each concern; flag conflicting/outdated sources | `search_regulations` |
| **3. Shopper Advocate** | **Audit agent 2**, apply the user's profile, find swaps, act | `find_alternatives`, `add_to_shopping_list` (only if the user allows) |

The **health score (0–100)** is computed in code (`backend/src/common/scoring.py`), not by the AI. It combines
NOVA processing level, Nutri-Score, watch-list additives (`backend/src/data/risk_table.json`) and personal
allergen / avoid / diet penalties. Browsing and searching cost **no** AI tokens; only "Run AI analysis" calls Bedrock.

**Cost:** everything is serverless and scales to zero. One AI analysis costs about $0.001 on Nova Lite, and a
week of class use should stay under $1. Run `make destroy` when the course ends.

## 10. Requirement map (for graders)

| RFP requirement | Where it is |
|---|---|
| ≥3 specialized agents with distinct prompts | `agents/prompts.py`, `agents/orchestrator.py` |
| Clear handoff / audit | Scout → Analyst → Advocate; the Advocate's `audit_notes` |
| Agent autonomously uses a tool (Lambda/API/DB) | `lookup_product` (API), `search_regulations`, `add_to_shopping_list` (DynamoDB) |
| ≥5 docs, 1 dense, raw, conflicting | `knowledge/sources.json`. Dense: OEHHA 2019 FSOR, 21 CFR 172. Conflicts: OEHHA 2018 vs 2019; FDA Red 3 (2025) vs 21 CFR 74.303; EU TiO₂ ban vs 21 CFR 73.575 |
| IaC | `infra/*.tf`, S3 remote state with native locking |
| CI/CD | `.github/workflows/ci.yml`, `deploy.yml` (repo root) |
| Security & Governance | `infra/governance.tf` (Guardrail), `infra/iam.tf` (per-function, per-ARN), Cognito JWT, user id taken only from the token |
| Observability | `infra/observability.tf` dashboard: per-agent tokens/latency/cost, cost per hour, job outcomes, errors |
| GUI with Thinking/Action states | `frontend/src/components/AgentTimeline.jsx` |

**Team split** (each coworker needs their own commits):
- Agents & prompts: `backend/src/agents`
- Data, scoring & search: `common/`, `knowledge/`, `scripts/`
- Infrastructure: `infra/`
- Website & CI/CD: `frontend/`, `.github/`

**Handling a "wrench":**
- New model: change the `model_id` variable.
- New store or aisle: edit `common/config.py`.
- New regulation: add it to `knowledge/sources.json` and run `make knowledge`.
- New concern: edit `risk_table.json`.
- Managed RAG: swap `common/kb.py` for Knowledge Bases for Bedrock.

Product data comes from [Open Food Facts](https://world.openfoodfacts.org) (ODbL, crowd-sourced; store tags are
incomplete). PhyTro is decision support, not medical advice.
