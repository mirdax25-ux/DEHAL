# B.1.2 rc.3 source snapshot provenance

Observed: 2026-10-03

This directory began as a source snapshot of an external Floot project. Its
application labels and helper filenames were subsequently renamed to B.1.2 for
consistency across this repository. It is therefore a derived, renamed copy and
is no longer byte-identical to the originally observed source. The remote code
is retained as an archived reference; it is not the active B.1.2 implementation.

## Source identity

- Floot project id: `905e0e5f-7cc6-432d-a0fb-d8d29e8d4b08`
- Floot project version observed: `1790993254039`
- Runtime server version in source: `1.2.0-rc.3`
- Runtime core version in source: `2.0.0-compatible`
- Runtime static core digest: `floot-ts-guard-loop-1.2.0-rc.3-20261003`

The source project identifier and observed version are retained from the original
capture. This renamed copy does **not** prove that the Floot project version
corresponds to any existing Git commit. The 2.1 integration line therefore adds
explicit runtime source/build provenance instead of retroactively inventing a
Git identity for rc.3.

## SHA-256 of renamed snapshot files

These hashes identify the current renamed files, not the original capture:
```text
3215381cac2be6bb735628af771f1ce7b0663352c5f304905e51cbbe3c4798c6  endpoints/health_GET.schema.ts
26ff3cf7d2997019eb33d0395963ece9af484c4f1129ceaa8e69bcd10c987315  endpoints/health_GET.ts
a8649da56ccaf49f8e9fbe8cb64c765be75b583bb0827475c287916298f05395  endpoints/mcp_POST.schema.ts
8e963aa4a69c90148612f525d4c1043900af2d176d58498384638fc2ac0c89ab  endpoints/mcp_POST.ts
cb93f700f7dbaa68eedf6b9d2d2175fa8157ea4c585a6834388831147b7961c8  helpers/B.1.2Core.spec.tsx
68f8ecb87de9c802b1bb494a425751fcb8a2610fa7caec0bb536bf79e401db01  helpers/B.1.2Core.tsx
4343a1a740f282d953f6688452ae7d8cea6aa6cb74ad7ec573a22f4cf7271bd5  helpers/McpGuardTool.spec.tsx
```

## Observed rc.3 failure modes that motivated 2.1

1. Pure direct counterevidence blocks the claim but remains classified as `UNKNOWN`; 2.1 introduces `REFUTED`.
2. The same source reference can be repeated in a claim and counted more than once; 2.1 uses unique evidence/source identity for verification and quorum.
3. Guard self-check can mark a critical unknown as merely reviewed and still proceed; 2.1 separates reviewed from resolved/blocking unknowns.
4. Health/runtime identity has a static digest but no verifiable Git commit/build binding; 2.1 adds runtime provenance receipts and a policy gate.
