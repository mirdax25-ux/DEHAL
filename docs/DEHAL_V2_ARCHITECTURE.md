# DEHAL v2 — arhitektura (dizajn 2026-11-07)

**Načelo:** jedina presuda dolazi iz determinističkog računa. Nedeterministički slojevi (LLM observer) mogu samo predložiti ESCALATE.

## Veto hijerarhija (nema ponderirane fuzije)

1. hard failed -> BLOCK
2. price uncovered -> BLOCK
3. corrupt snapshot -> ESCALATE
4. quorum disagreement -> ESCALATE
5. raw_text contradiction -> ESCALATE
6. observer conflict -> ESCALATE (advisory)
7. else -> APPROVE

## Ključne odluke (nalazi A-E iz pregleda DeepSeekovog pseudokoda)

- A: LLM-judge izbačen iz BLOCK logike; observer je savjetnik.
- B: ponderirana fuzija (0.4/0.3/0.3) zamijenjena veto hijerarhijom; lijep
  format ne može kupiti prolaz.
- C: numeric_match s tolerancijom po valuti umjesto substring contains;
  NaN/inf guard; rasponi po valuti.
- D: fetch()/now() izvan jezgre: snapshoti dolaze s SHA-256, evaluation_time
  je parametar.
- E: svaki verdikt nosi claim_hash + evidence_hashes (reproducibilnost).

## Granice (iskreno)

extract_numbers je konzervativan parser brojeva, ne potpuni financijski
parser; snapshoti s brojevima koji nisu cijena mogu lažno kontradiktirati
(kvorum se tada ponaša strogo prema fail-closed: ESCALATE, ne APPROVE).
Poznata ograničenja, dokumentirana namjerno.

## Test obaveze (tests/test_dehal_v2.py)

1. izmišljena cijena + savršen format -> BLOCK
2. NaN -> BLOCK
3. substring preljev (1342.37 vs 342.37) -> BLOCK
4. observer konflikt uvijek ESCALATE, nikad BLOCK
5. 10 pokretanja -> byte-identični verdikti
