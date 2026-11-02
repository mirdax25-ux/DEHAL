# B.1.2 2.1 — algoritam i granice odgovornosti

## Temeljno pravilo

**DETERMINISTIČKI ULAZ → NEDETERMINISTIČKA PRIPREMA → DETERMINISTIČKA PROVJERA → RECEIPT**

B.1.2 ne smije pretvoriti nedeterminističku pripremu u autoritet istine. Semantička priprema, retrieval, atomizacija ili kandidiranje može koristiti model/Logic/PRECICA, ali finalni verifier radi samo nad strukturiranim ugovorom i dokazima.

## Faza A — deterministički ulaz

1. Normaliziraj transportni JSON i odbij nevaljane tipove.
2. Validiraj jedinstvene claim/evidence identitete.
3. Validiraj provenance polja, timestampove, hashove i policy verziju.
4. Veži claim uz:
   - claim type
   - authority scope
   - answerability status
   - risk
   - consequential flag
5. Veži evidence uz:
   - evidence id
   - source id
   - source role
   - evidence origin
   - authority scope
   - observed_at
   - directness
   - post-action status
   - optional source/content hash
6. Kanoniziraj conversation contract: goal, referent i aktivna ograničenja.
7. Izračunaj reproducibilne hashove ulaza/ugovora gdje je primjenjivo.

Ako bilo koji obavezni deterministički preduvjet nije zadovoljen, fail-closed.

## Faza B — nedeterministička priprema

Ova faza je izvan autoriteta finalne klasifikacije. Dopušteno je:
- atomizirati raw model output,
- predlagati claim type,
- tražiti dokaze,
- koristiti memoriju i alate,
- generirati alternativne kandidate,
- predlagati referent/cilj/constraint mapping,
- koristiti BodulLogic i PRECICU.

Rezultat je samo **kandidat + strukturirani contract**, nikad konačni FACT.

## Faza C — deterministička provjera

### C1. Answerability gate

- ANSWERABLE → nastavi
- NEEDS_CLARIFICATION → ESCALATE
- UNDERSPECIFIED / FALSE_PREMISE / OUT_OF_SCOPE / PARTIALLY_ANSWERABLE → BLOCK dok policy ne definira poseban partial režim
- CONTRADICTORY_INPUT → CONFLICT

### C2. Conversation gate

Kandidat mora imati isti:
- goal_id
- referent_id

Sva aktivna constraints moraju biti zadovoljena.

### C3. Evidence eligibility

Dokaz je kandidat za provjeru samo ako:
- eligible=true,
- timestamp je timezone-aware,
- nije iz budućnosti kada policy to zabranjuje,
- nije stariji od max_age,
- identitet je jedinstven.

### C4. Authority gate

Porijeklo i authority scope moraju odgovarati vrsti tvrdnje.

Primjeri:
- USER_ASSERTION ne može sam dokazati EXTERNAL_FACT.
- USER_PREFERENCE može dokazati USER_PREFERENCE unutar tog scopea.
- USER_INSTRUCTION može dokazati aktivnu korisničku instrukciju.
- TOOL_OBSERVATION / EXTERNAL_SOURCE / COMPUTED_RESULT mogu biti dokaz za vanjske tvrdnje samo uz pripadajući policy i provenance.

### C5. Epistemološka klasifikacija

Za autorizirane, svježe dokaze:

- 0 supporting + 0 contradicting → UNKNOWN
- supporting > 0 + contradicting = 0:
  - direct observation → FACT
  - indirect → INFERENCE
  - claim type inference → INFERENCE
  - claim type estimate → ESTIMATE
- supporting = 0 + contradicting > 0 → REFUTED
- supporting > 0 + contradicting > 0 → CONFLICT

### C6. Action-state gate

ACTION_STATE zahtijeva:
- fresh direct post-action dokaz,
- kada policy traži: neovisni verifier/external source.

### C7. Source-independence gate

Quorum se računa po povezanim grupama dokaza, ne po broju evidence objekata.
Zajednički `source_id`, `source_ref` ili `independence_group` povezuju dokaze,
uključujući tranzitivno preklapanje. Dodatni metapodaci mogu spojiti identitete,
ali ne mogu razdvojiti već poznat izvor na više glasova. Vrijednosti se uspoređuju
nakon uklanjanja rubnih razmaka, unutar istog polja. Ovo ne autentificira vanjski
izvor i ne podrazumijeva normalizaciju različitih URL-ova.

### C8. Unknown gate

Self-check razlikuje:
- reviewed
- resolved
- blocking
- severity

Critical ili blocking unknown koji nije resolved → ESCALATE/BLOCK.
**reviewed ≠ resolved**.

### C9. Risk / human gate

High-risk remote caller ne može sam tvrditi da je ljudsko odobrenje verificirano. Neautentificirano `human_approved=true` mora fail-close prema transport policyju.

### C10. Runtime provenance gate

Ako policy zahtijeva runtime provenance, build mora imati:
- source commit
- source ref
- build id

Bez toga → BLOCK `runtime_provenance_unverified`.

## Faza D — deterministički receipt

Receipt mora sadržavati najmanje:
- algorithm/schema/policy version
- claim metadata
- classification
- verdict + reason
- evidence ids i source ids
- evidence origins i authority scopes
- supporting / contradicting / authority-rejected evidence
- post-action i independence gates
- runtime provenance
- receipt SHA-256

## Faza E — evolucija nakon kvara

Potvrđeni kvar se zapisuje:

**FAILURE MODE → ROOT CAUSE → GUARDRAIL → REGRESSION TEST → VERSION CHANGE**

Novi release ne smije izgubiti prethodni prolaz bez eksplicitnog objašnjenja.

## Benchmark regresije iz stvarnog razgovora

- BH-REFUTED-001 — direktni counterevidence ne smije biti UNKNOWN.
- BH-AUTHORITY-001 — korisničko “oko 30” ne smije postati vanjska činjenica bez neovisnog dokaza.
- BH-AUTHORITY-002 — korisnikova vlastita preference/instruction može biti autoritativna unutar pripadajućeg scopea.
- BH-UNKNOWN-BLOCK-001 — reviewed critical unresolved unknown mora eskalirati/blokirati.
- BH-REFERENT-001 — kandidat za tri B.1.2 prijave ne smije proći s referentom PRECICA.
- BH-CONSTRAINT-001 — aktivni hrvatski/latinica constraint mora biti zadovoljen.
- BH-PROVENANCE-001 — release policy može zahtijevati dokazivi source/build identitet.
- BH-SOURCE-INDEPENDENCE-001 — dvije evidence instance istog source_id ne zadovoljavaju quorum.
- BH-INDEPENDENCE-002 ? razli?iti source_id aliasi istog source_ref / independence_group ne zadovoljavaju quorum.

## Kompatibilnost

2.1 uvodi schema v3. Stari klijenti mogu nastaviti slati postojeća polja jer nova polja imaju fail-safe zadane vrijednosti gdje to ne slabi sigurnost. Breaking promjene prema live Floot/native transportu ne smiju biti objavljene bez zasebne kompatibilnosne matrice i post-action testa.
