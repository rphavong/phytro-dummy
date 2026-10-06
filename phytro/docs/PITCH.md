# PhyTro — 2-minute elevator pitch

**The action gap (15 s).** A shopper in the cereal aisle faces 60 boxes. The facts that matter — a dye the FDA just
revoked, an additive the EU banned, a sweetener IARC flagged — are buried in 500-page regulations and crowd-sourced
labels. Nobody reads them in the aisle, so people buy on marketing.

**Our ALA (35 s).** PhyTro is an Autonomous Liaison Agent built on AWS Bedrock with three specialists:
the **Label Scout** pulls clean facts out of messy label data, the **Toxicology Analyst** cites FDA, EU and
California Prop 65 documents — and flags when they *conflict*, like the 2018 vs 2019 coffee rules or Red No. 3's
2025 revocation versus the older codified listing — and the **Shopper Advocate** audits the analyst, applies the
user's allergies and diet, and *acts*: it finds a healthier product at Walmart or Target and puts it on the user's
shopping list.

**Demo (40 s).** Sign in → Coffee aisle at Walmart → ranked list, healthiest first → open a flavored creamer coffee →
Run AI analysis → watch the three agent lanes think and call tools live → verdict with sources and a conflict note →
the swap appears on My List.

**Engineering (20 s).** Terraform for everything; GitHub Actions tests, applies and smoke-tests on every push;
Bedrock Guardrails screen untrusted label text for prompt injection and block medical-diagnosis answers; least-privilege
IAM per function; a CloudWatch dashboard shows tokens, latency and dollar cost per agent.

**Why it wins (10 s).** Serverless and scale-to-zero: an analysis costs about a tenth of a cent, browsing costs nothing,
and a new regulation, store or model is a one-line change — ready for any wrench you throw at us.
