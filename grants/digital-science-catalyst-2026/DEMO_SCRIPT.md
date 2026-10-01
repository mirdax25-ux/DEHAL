# Catalyst Live Demo Script

## Goal

Show one bounded research workflow in which the verifier must approve, block, detect conflict and escalate.

## 1. Open with the problem

“Research agents can produce multi-step outputs, but the user still needs to know which claims are evidenced, uncertain, contradictory, or awaiting human approval.”

## 2. Show the fixture

Open:
`examples/research_fixture.json`

Explain that the fixture contains five deliberately different claim states:
1. supported claim
2. unsupported claim
3. contradictory evidence
4. action claim without final-state evidence
5. high-risk claim without human approval

## 3. Run the research demo

Command:

```bash
python examples/research_demo.py
```

Expected visible outcomes:

- supported → FACT / APPROVE
- missing evidence → UNKNOWN / BLOCK
- contradiction → CONFLICT / BLOCK
- unverified action completion → FACT / BLOCK
- high-risk claim → FACT / ESCALATE

Point out:
the system does not force every uncertain case into a yes/no answer.

## 4. Show one evidence receipt

Open the result for the supported or action-state claim.

Show:
- claim ID
- evidence source ID
- timestamp
- directness
- contradiction state
- post-action state
- human-gate state
- algorithm version
- policy version
- final verdict

Key sentence:
“An executor saying it finished is not evidence that the final state exists.”

## 5. Run the evaluation harness

Command:

```bash
python examples/evaluation_demo.py
```

Expected reference output:

- automatic disposition rate: 0.60
- human-attention rate: 0.40
- evidence coverage: 0.80
- unsupported block rate: 1.00
- contradiction detection rate: 1.00
- action false-positive approve rate: 0.00
- high-risk unauthorized approve rate: 0.00

Say explicitly:
“These are five-case fixture results, not general accuracy claims.”

## 6. Show the failure history

Open:
`CHANGELOG.md`

Show the Error → Evolution pattern:

FAILURE MODE
→ ROOT CAUSE
→ GUARDRAIL
→ REGRESSION TEST
→ VERSION CHANGE

This demonstrates that the system records what failed and converts it into a testable guardrail.

## 7. Close with integration direction

Current:
Python core + strict JSON adapter.

Next:
API/MCP verification service embedded inside an existing research-agent or evidence-synthesis workflow.

Human remains accountable for high-risk or conflicting decisions.
