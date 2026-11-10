# v2_reference - nezavisna referentna implementacija (2026-11-10)

Ovu jezgru napisao je Vibe/GLM agent NE gledajuci postojeću `dehal/` v2 implementaciju,
radi nezavisnog usporednog razaranja (pravilo: "skripta nije gotova dok je ne razoruje
netko tko je nije pisao").

- `dehal_core.py` - deterministička jezgra: APPROVE/BLOCK/ESCALATE, fail-closed,
  LLM smije samo predložiti ESCALATE (grounding ima veto), fetch/now izvan jezgre,
  SHA-256 provenancija.
- `test_dehal_core.py` - 5 obaveznih testova (radi pod pytest-om i samostalno:
  `python3 test_dehal_core.py`).

Status: NEPROVJERENO. Logika je izvršena u TypeScript okruženju (5/5 PASS),
Python port nije izvršen do objave. Referentni rezultati TS izvedbe:
- T1 APPROVE, hash 464bdec0fd6fbb8c1d1a383c026881e2e640035d86f4cd6d69b6ff7ab7032ff4
- T2 BLOCK (R_CONTRADICTION + R_LLM_ESCALATE_VETOED_BY_GROUNDING)
- T3 ESCALATE (R_FLAG_ESCALATE)
- T4 BLOCK (R_NO_EVIDENCE_FAIL_CLOSED + R_LLM_PROPOSAL_REJECTED_ONLY_ESCALATE_ALLOWED)
- T5 BLOCK + SHA-256 vektor sha256("abc") potvrđen

Ako Python port da iste verdikte i hash T1 za iste ulaze, implementacije su
međusobno potvrđene. Ako ne - razlika je bug u jednoj od njih.
