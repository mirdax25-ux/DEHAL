# Floot rc.3 source snapshot provenance

Observed: 2026-10-03

This directory is an immutable source snapshot copied from the current Floot project that serves the live BodulHal 1.2.0-rc.3 implementation.

## Source identity

- Floot project id: `905e0e5f-7cc6-432d-a0fb-d8d29e8d4b08`
- Floot project name: `BodulHal 1.1.2 MCP`
- Floot project version observed: `1790993254039`
- Runtime server version in source: `1.2.0-rc.3`
- Runtime core version in source: `2.0.0-compatible`
- Runtime static core digest: `floot-ts-guard-loop-1.2.0-rc.3-20261003`

This snapshot proves which source text was observed in Floot at the stated project version. It does **not** prove that the Floot project version corresponds to any existing Git commit. The new 2.1 integration line therefore adds explicit runtime source/build provenance instead of retroactively inventing a Git identity for rc.3.

## SHA-256 snapshot

```text
3215381cac2be6bb735628af771f1ce7b0663352c5f304905e51cbbe3c4798c6  endpoints/health_GET.schema.ts
8c613a4859d7a5f0be10c0a9715c767197f44cb103d0d0cd4d1b39ce8242d241  endpoints/health_GET.ts
a8649da56ccaf49f8e9fbe8cb64c765be75b583bb0827475c287916298f05395  endpoints/mcp_POST.schema.ts
95c3a5470931982d43413abbd3fd83b0a726d6c279cecbd949b25f16b0086f40  endpoints/mcp_POST.ts
e929ccc6952d461d307a5d958522859af98923802b6252e06d97e360dbb23617  helpers/BodulHalCore.spec.tsx
d9ce705cc669e979612b7110eae09e021a0b555e4c6a2d8425a0206fd138bc98  helpers/BodulHalCore.tsx
20963c1ba15ad47d18e7d537661468cf0c35a13e2c6c53668fa7442f4cddccd1  helpers/McpGuardTool.spec.tsx
```

## Observed rc.3 failure modes that motivated 2.1

1. Pure direct counterevidence blocks the claim but remains classified as `UNKNOWN`; 2.1 introduces `REFUTED`.
2. The same source reference can be repeated in a claim and counted more than once; 2.1 uses unique evidence/source identity for verification and quorum.
3. Guard self-check can mark a critical unknown as merely reviewed and still proceed; 2.1 separates reviewed from resolved/blocking unknowns.
4. Health/runtime identity has a static digest but no verifiable Git commit/build binding; 2.1 adds runtime provenance receipts and a policy gate.
