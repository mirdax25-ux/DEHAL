# Digital Science Catalyst Grant 2026 — B.1.2

## 1. THE PROBLEM

Research agents are increasingly able to search, extract, synthesize and act across several steps, but their outputs are still hard to trust at the point where a person or institution must make a decision. A fluent agent can blur together direct evidence, inference, estimates, missing evidence and conflicting evidence. The practical cost is not only hallucinated text: it is duplicated checking, unclear accountability, and the risk that an agent reports an action or research state as complete when the final state was never independently verified.

B.1.2 is aimed at researchers, research teams, publishers and institutions using multi-step AI workflows. Today, users typically re-open sources, inspect citations manually, re-run searches, or rely on the same agent that produced the answer to explain why it should be trusted. The problem appears every time an AI-generated research output must cross from “helpful draft” into a decision, publication, evidence synthesis, funding workflow or other accountable process.

## 2. YOUR WORKFLOW

B.1.2 is an independent verification layer that sits between an agent’s work and the final accepted output.

The current reference flow is:

RESEARCH REQUEST → CLAIMS → EVIDENCE → VERIFICATION → EVIDENCE RECEIPTS → HUMAN/ESCALATION GATE → FINAL REPORT.

First, an agent or upstream workflow produces bounded claims. Each claim is checked against supplied evidence using explicit rules for freshness, directness, contradiction and action state. Claims are classified as FACT, INFERENCE, ESTIMATE, UNKNOWN or CONFLICT, and receive APPROVE, BLOCK or ESCALATE verdicts.

Autonomous steps include structured evidence evaluation, contradiction detection, post-action checking, metrics and receipt generation. Human review is required where policy calls for escalation, especially high-risk actions or conflicting evidence. Human approval never converts missing evidence into fact.

Today the prototype is exposed through a Python core and strict JSON adapter. The first pilot integration target is an MCP-compatible research assistant or evidence-synthesis workflow used by researchers. That external integration is not yet implemented. The goal is for verification to run inside the existing research workflow rather than as a separate manual step.

## 3. TRUST, AUDIT AND GOVERNANCE

Every result includes a machine-readable evidence receipt containing the claim, classification, verdict, evidence identities, timestamps, directness, contradiction state, post-action state, human-gate state, algorithm version and policy version.

The core rule is: CONFIDENCE <= EVIDENCE.

Missing eligible evidence becomes UNKNOWN rather than a guessed answer. Eligible contradictory evidence becomes CONFLICT. A consequential action claim cannot be approved without fresh direct post-action/final-state evidence. A high-risk fact cannot pass the human gate without explicit approval.

The current deterministic research fixture deliberately includes tasks the system should refuse, block or escalate. In the reference benchmark, an unsupported claim is BLOCKED, contradictory evidence produces CONFLICT/BLOCK, an unverified action completion is BLOCKED, and a high-risk claim without human approval is ESCALATED.

Accountability remains with the human owner or institution. B.1.2 records why a claim passed or did not pass; it does not remove the need for domain judgment or claim that supplied evidence is automatically authentic.

## 4. TEAM

The project is founder-led. The work to date has combined AI orchestration, local and cloud model workflows, verification architecture, failure analysis, TDD, CI, and human-approval design. The project emerged from repeated practical failures where “command sent,” “model said so,” or “HTTP 200” were treated as equivalent to verified completion.

The operating discipline is failure-driven: FAILURE MODE → ROOT CAUSE → GUARDRAIL → REGRESSION TEST → VERSION CHANGE.

No external advisors are being claimed at this stage.

## 5. WHERE YOU ARE TODAY

B.1.2 is a working reference prototype, not a production deployment.

The current GitHub implementation includes a deterministic verification core, a strict JSON adapter, a reproducible research-agent evidence demo and a v1.3 evaluation harness. The current test suite has 53 passing tests, with GitHub CI passing on Python 3.10, 3.11 and 3.13. The final CI workflow installs the package, compiles it, runs the full suite, runs the research demo and runs the evaluation harness.

On the bundled five-claim benchmark, the measured results are:

- automatic disposition rate: 0.60
- human-attention rate: 0.40
- evidence coverage: 0.80
- unsupported-claim block rate: 1.00
- contradiction detection rate: 1.00
- action-completion false-positive rate: 0.00
- high-risk-without-human-approval approve rate: 0.00

These are bounded results on a tiny deterministic fixture, not general accuracy claims. No timed human-effort study has been performed.

## 6. ALTERNATIVES AND COMPETITORS

Several strong products address adjacent parts of the problem. Scite grounds research answers in scientific literature and exposes supporting or contrasting citation evidence. Elicit provides agentic research, evidence synthesis, systematic-review workflows and auditable source-linked outputs. ResearchRabbit focuses on literature discovery and navigating relationships between papers.

B.1.2 is not intended to replace these systems. Its focus is narrower: an independent policy and evidence gate that can sit after an agent or research workflow and decide whether a bounded claim may be accepted, blocked or escalated. The differentiation we are testing is the separation of executor from verifier, explicit UNKNOWN/CONFLICT states, post-action verification, human gates, deterministic receipts and regression-driven guardrails.

A broader prior-art and competitor review is still required before making any novelty claim.

## 7. WHERE THIS GOES

The longer-term product is a reusable verification and governance layer for research agents and multi-agent systems. It should be deployable as an API/MCP service inside research, publishing, evidence-synthesis and institutional decision workflows.

A commercial model could combine an open verification core with paid hosted infrastructure, enterprise governance, integration support, audit retention, policy management and organization-specific evaluation packs. Pricing has not yet been validated; we would test usage-based and organization-level subscription models with pilot users.

## 8. FIT WITH DIGITAL SCIENCE

B.1.2 sits primarily in evidence synthesis, research integrity and institutional decision workflows. The intended users are researchers, publishers, funders and research organizations deploying agentic AI where provenance and accountability matter.

The 2026 Catalyst theme is unusually well matched to the problem we are solving: multi-step AI that acts on research, with audit trails, governance and provenance. Digital Science’s recent Dimensions and Altmetric MCP work also makes the fit concrete: trusted research data can enter an agentic workflow through MCP, while B.1.2 can test whether downstream claims and actions are sufficiently evidenced to approve, block or escalate. We would value Digital Science’s research-software experience, access to real workflow feedback, and guidance on testing this verification layer inside systems researchers already use rather than building another isolated AI interface.

## 9. BUDGET

We would request up to £25,000 for a focused validation and integration programme:

- £8,000 — production-grade verification API/MCP integration and provenance adapters
- £5,000 — larger independently labelled evaluation set and external researcher testing
- £4,000 — evidence-receipt and human-review UX
- £3,000 — security, policy and audit-log hardening
- £3,000 — integrations with existing research-agent/evidence-synthesis workflows
- £2,000 — documentation, packaging, deployment and pilot support

The grant would let us move from a deterministic reference prototype to a tested research-workflow pilot with external users, broader evaluation data and integration evidence.
