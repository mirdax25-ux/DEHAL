# DEHAL (formerly BodulskiHal Core)

DEHAL — **DE**tecting **HAL**lucinations. Python verification engine for structured claims and supplied evidence. It classifies support, contradiction and uncertainty and returns APPROVE, BLOCK or ESCALATE.

## Quick start

Requires Python 3.10 or newer.

```bash
git clone https://github.com/mirdax25-ux/Brutala-Hal-.git
cd Brutala-Hal-
python -m pip install -e ".[test]"
python examples/demo.py
python examples/research_demo.py
python examples/evaluation_demo.py
```

Each demo uses checked-in fixtures. No model account or API key is required for these examples.

## Architecture

| Path | Responsibility |
| --- | --- |
| `bodulskihal_core/engine.py` | Claim types, evidence policy and verdicts |
| `adapter.py`, `ingestion.py`, `raw_pipeline.py` | Structured-input ingestion |
| `guard_loop.py`, `conversation_gate.py` | Guard and conversation contracts |
| `runtime_provenance.py` | Runtime source/ref/build identity |
| `examples/` | Runnable examples and fixtures |
| `tests/` | Unit, adversarial and contract regression checks |
| `remote/floot_rc3/` | Historical remote source snapshot |

Paths without a directory prefix above are inside `bodulskihal_core/`.

## Verification and packaging

```bash
python -m pytest
python -m compileall -q bodulskihal_core
python -m pip install build
python -m build
```

See [verification record](docs/VERIFICATION.md) for executed checks and [algorithm overview](docs/ALGORITHM_OVERVIEW.md) for the detailed rules.

## Versions and boundaries

Core/package version: 2.1.2. The Python core, historical Floot snapshot and separate live MCP services have independent versions. A health response alone does not establish source parity.

Supplied JSON is evidence content, not proof of the source's authenticity. This engine does not independently certify arbitrary prose, all hallucinations, or an external action. The OAuth transport candidate remains on `feature/bodulhal-oauth-guard-20261012`; it is a service variant, not a separately verified product in this package.

**Naming decision (2026-11-07):** product name is DEHAL. Repository rename `Brutala-Hal-` → `DEHAL` follows via GitHub Settings; GitHub will redirect old URLs automatically.

## License

[Apache License 2.0](LICENSE). Attribution information is in [NOTICE](NOTICE). Dependencies retain their respective licenses.
