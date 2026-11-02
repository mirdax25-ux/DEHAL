# B.1.2

Deterministički evidence-first verifier za AI/agent tvrdnje.

## Trenutačni integracijski kandidat

- **Core algoritam:** 2.1.2
- **JSON adapter:** schema 3
- **Paket:** 2.1.2
- **Guard Loop:** 2.0.0 kompatibilna jezgra, proširena strukturiranim unknown zapisima
- **Grana:** `main`
- **Provjera:** testovi i CI moraju odgovarati točnom commitu; povijesni broj testova nije status trenutačne verzije.

Ovo nije još release tvrdnja. GitHub CI, neovisni pregled, post-action provjera i eventualni live rollout ostaju zasebni gateovi.

## Arhitektonsko pravilo

**DETERMINISTIČKI ULAZ → NEDETERMINISTIČKA PRIPREMA → DETERMINISTIČKA PROVJERA → RECEIPT**

Nedeterministička priprema može koristiti BodulLogic, PRECICU, modele, memoriju i alate. Ona stvara kandidatni strukturirani ugovor, ne konačnu istinu. B.1.2 daje završnu klasifikaciju samo iz strukturiranih ulaza i dokaznih pravila.

Detaljna specifikacija: `docs/B.1.2_ALGORITHM.md`.

Distribucijski naziv projekta i Python modul su `B.1.2` (`b_1_2_core`).

## Klasifikacije

- `FACT`
- `INFERENCE`
- `ESTIMATE`
- `UNKNOWN`
- `REFUTED`
- `CONFLICT`

Verdicti:

- `APPROVE`
- `BLOCK`
- `ESCALATE`

## Najvažniji hard gateovi

1. Nedostatak prihvatljivog dokaza ne može postati FACT.
2. Čisti prihvatljivi counterevidence daje REFUTED.
3. Istodobna podrška i counterevidence daju CONFLICT.
4. INFERENCE i ESTIMATE ne glume FACT.
5. ACTION_STATE zahtijeva svjež direktan post-action dokaz; policy može zahtijevati neovisni verifier/external izvor.
6. USER_ASSERTION ne može sam certificirati EXTERNAL_FACT.
7. USER_PREFERENCE / USER_INSTRUCTION vrijede samo unutar pripadajućeg authority scopea.
8. Critical ili blocking unknown koji nije resolved ne prolazi samo zato što je reviewed.
9. Conversation contract provjerava goal, referent i aktivne constraints.
10. High-risk remote human approval ostaje fail-closed dok odobrenje nije autentificirano.
11. Duplicate claim/evidence identiteti i nevaljani runtime tipovi fail-close.
12. Policy može zahtijevati dokazivi runtime source commit/ref/build id.
13. Ingestion authority mora biti `TypeAuthority`; lifecycle approval/checkpoint flagovi moraju biti pravi booleans.
14. Zajednički source ID, source ref ili independence group povezuju dokaze u jednu grupu; dodatni aliasi ne povećavaju quorum.

## Porijeklo i autoritet dokaza

Evidence nosi odvojeno:

- `origin`: external source, tool observation, computed result, memory, user assertion, user self-report, user preference ili user instruction
- `authority_scope`: external fact, system state, user self-report, user preference ili user instruction

Porijeklo nije isto što i istinitost. Autoritet se procjenjuje deterministički prema vrsti tvrdnje.

## Answerability

Claim može biti:

- ANSWERABLE
- PARTIALLY_ANSWERABLE
- UNDERSPECIFIED
- FALSE_PREMISE
- CONTRADICTORY_INPUT
- NEEDS_CLARIFICATION
- OUT_OF_SCOPE

Nedovoljno definiran input ne smije se pretvoriti u izmišljeni odgovor.

## Conversation contract

`conversation_gate.py` provjerava:

- aktivni cilj,
- aktivni referent,
- kandidatni cilj/referent,
- aktivna strukturirana ograničenja.

To je deterministic output gate. Semantičko određivanje referenta/cilja ostaje u upstream pripremi, npr. BodulLogicu.

## Runtime provenance

Svaki receipt uključuje runtime provenance:

- `B_1_2_SOURCE_COMMIT`
- `B_1_2_SOURCE_REF`
- `B_1_2_BUILD_ID`

Ako policy postavi `require_runtime_provenance=true`, neidentificirani build se blokira.

GitHub CI automatski postavlja ova polja iz GitHub run konteksta.

## Floot rc.3 audit snapshot

`remote/floot_rc3/` sadrži preimenovanu arhivsku kopiju izvornog sourcea Floot
rc.3 servisa i ažurirani SHA-256 manifest. Porijeklo i ograničenja kopije
dokumentirani su u `remote/floot_rc3/REMOTE_PROVENANCE.md`.

Taj snapshot potvrđuje koji je source opažen u Floot projektu/versionu, ali ne izmišlja retroaktivnu Git commit vezu koja tada nije postojala.

## Testovi

```bash
python -m pytest
```

Benchmark regresije su u:

`tests/test_benchmark_regressions.py`

i pokrivaju REFUTED, user-anchor authority, source independence, structured unknowns, referent/constraint gate i runtime provenance.

## Granica tvrdnji

Ovaj projekt ne tvrdi da:

- otkriva sve halucinacije,
- supplied evidence automatski znači autentičan vanjski izvor,
- jedan benchmark generalizira na sve modele,
- Logic/Hal uzrokuju poboljšanje bez kontroliranog A/B testa,
- cijeli BodulAI sustav jest production-ready samo zato što core testovi prolaze.
