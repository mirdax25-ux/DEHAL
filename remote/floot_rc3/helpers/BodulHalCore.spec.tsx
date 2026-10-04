import { CORE_VERSION, MAX_CANONICAL_TOOL_INPUT_BYTES, SERVER_VERSION, canonicalJsonByteLength, guardClaim, health, jsonDepth, verifyClaims, verifyManifest } from "./BodulHalCore";

describe("BodulHal 1.2.0-rc.3 remote contract", () => {
  const now = new Date("2026-09-27T16:30:00Z");
  const ts = "2026-09-27T16:29:55Z";
  const doc = { status:"ok", version:SERVER_VERSION, core_version:CORE_VERSION, max_claims:20 };
  const claim = (extra:any = {}) => ({ id:"health_status", kind:"observation", assertion:{op:"json_equals",pointer:"/status",expected:"ok"}, sources:[{type:"supplied",id:"health"}], max_age_seconds:300, ...extra });
  const ev = (extra:any = {}) => ({ id:"health", data:doc, observed_at:ts, ...extra });

  it("reports release 1.2.0-rc.3", () => expect(health(now).version).toBe("1.2.0-rc.3"));
  it("blocks unsupported free text", () => expect(verifyClaims([{id:"x",kind:"text",text:"done"}],[],now).status).toBe("BLOCK"));
  it("approves matching bounded JSON", () => expect(verifyClaims([claim()],[ev()],now).classification).toBe("FACT"));
  it("verify_manifest preserves the same gate", () => expect(verifyManifest({schema_version:1,claims:[claim()]},[ev()],now).approved).toBe(true));
  it("detects conflict", () => {
    const c = claim({sources:[{type:"supplied",id:"health"},{type:"supplied",id:"bad"}]});
    const r = verifyClaims([c],[ev(),{id:"bad",data:{status:"bad"},observed_at:ts}],now);
    expect(r.classification).toBe("CONFLICT");
  });
  it("blocks missing timestamps", () => expect(verifyClaims([claim()],[{id:"health",data:doc}],now).status).toBe("BLOCK"));
  it("blocks stale evidence", () => expect(verifyClaims([claim({max_age_seconds:1})],[{id:"health",data:doc,observed_at:"2026-09-27T16:29:00Z"}],now).status).toBe("BLOCK"));
  it("uses strict JSON types", () => expect(verifyClaims([claim({assertion:{op:"json_equals",pointer:"/max_claims",expected:"20"}})],[ev()],now).approved).toBe(false));
  it("rejects observation text hitchhiking", () => expect(verifyClaims([claim({text:"done"})],[ev()],now).reason).toBe("invalid_input"));
  it("rejects remote file sources", () => expect(verifyClaims([claim({sources:[{type:"file",path:"x"}]})],[],now).reason).toBe("invalid_input"));
  it("enforces post-action boundary", () => expect(verifyClaims([claim({after:"2026-09-27T16:29:59Z"})],[ev()],now).approved).toBe(false));

  it("rejects risk metadata outside guard_claim", () => {
    const r = verifyClaims([claim({risk:"high"})],[ev()],now);
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("invalid_input");
  });

  it("rejects naive evidence timestamps without timezone", () => {
    const r = verifyClaims([claim()],[ev({observed_at:"2026-09-27T16:29:55"})],now);
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("invalid_input");
  });

  it("rejects naive post-action timestamps without timezone", () => {
    const r = verifyClaims([claim({after:"2026-09-27T16:29:50"})],[ev()],now);
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("invalid_input");
  });

  it("rejects duplicate claim identities", () => {
    const r = verifyClaims([claim(),claim()],[ev()],now);
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("invalid_input");
  });

  it("enforces canonical tool input at 128 KiB", () => {
    const atLimit:any = { claims:[{id:"x",kind:"text",text:""}], evidence:[] };
    const emptyBytes = canonicalJsonByteLength(atLimit)!;
    atLimit.claims[0].text = "x".repeat(MAX_CANONICAL_TOOL_INPUT_BYTES - emptyBytes);
    expect(canonicalJsonByteLength(atLimit)).toBe(MAX_CANONICAL_TOOL_INPUT_BYTES);
    expect(verifyClaims(atLimit.claims, atLimit.evidence, now).reason).not.toBe("invalid_input");
    atLimit.claims[0].text += "x";
    expect(canonicalJsonByteLength(atLimit)).toBe(MAX_CANONICAL_TOOL_INPUT_BYTES + 1);
    expect(verifyClaims(atLimit.claims, atLimit.evidence, now).reason).toBe("invalid_input");
  });
  it("enforces JSON depth 16", () => {
    const nested = (levels:number) => {
      let value:any = "leaf";
      for (let i=0;i<levels;i++) value = { n:value };
      return value;
    };
    const make = (levels:number) => {
      const value = nested(levels);
      const c = claim({ assertion:{op:"json_equals",pointer:"/v",expected:value} });
      const e = ev({ data:{v:value} });
      return { c, e, args:{claims:[c],evidence:[e]} };
    };
    const d16 = make(12);
    const d17 = make(13);
    expect(jsonDepth(d16.args)).toBe(16);
    expect(jsonDepth(d17.args)).toBe(17);
    expect(verifyClaims([d16.c],[d16.e],now).approved).toBe(true);
    expect(verifyClaims([d17.c],[d17.e],now).reason).toBe("invalid_input");
  });

  const selfCheck = (extra:any = {}) => ({
    realism:"possible",
    known:["bounded claim is present"],
    assumptions:[],
    unknowns:[],
    assumptions_reviewed:true,
    unknowns_reviewed:true,
    ...extra,
  });

  it("guard_claim blocks impossible self-check before verification", () => {
    const r = guardClaim({ claim:claim(), evidence:[ev()], self_check:selfCheck({realism:"impossible"}) }, now);
    expect(r.stage).toBe("self_check");
    expect(r.classification).toBe("UNKNOWN");
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("self_check_impossible");
    expect(r.verification).toBeNull();
  });

  it("guard_claim escalates uncertain self-check", () => {
    const r = guardClaim({ claim:claim(), evidence:[ev()], self_check:selfCheck({realism:"uncertain",unknowns:["external state not checked"]}) }, now);
    expect(r.stage).toBe("self_check");
    expect(r.classification).toBe("UNKNOWN");
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("self_check_uncertain");
  });

  it("guard_claim escalates unreviewed assumptions", () => {
    const r = guardClaim({ claim:claim(), evidence:[ev()], self_check:selfCheck({assumptions:["provider reachable"],assumptions_reviewed:false}) }, now);
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("assumptions_not_reviewed");
  });

  it("guard_claim delegates possible reviewed claims to bounded verifier", () => {
    const r = guardClaim({ claim:claim(), evidence:[ev()], self_check:selfCheck() }, now);
    expect(r.stage).toBe("verification");
    expect(r.classification).toBe("FACT");
    expect(r.status).toBe("APPROVE");
    expect(r.verification.status).toBe("APPROVE");
  });

  it("guard_claim preserves missing evidence as UNKNOWN/BLOCK", () => {
    const r = guardClaim({ claim:claim(), evidence:[], self_check:selfCheck() }, now);
    expect(r.stage).toBe("verification");
    expect(r.classification).toBe("UNKNOWN");
    expect(r.status).toBe("BLOCK");
  });

  it("guard_claim blocks action_state without final-state boundary", () => {
    const action = claim({kind:"action_state"});
    const r = guardClaim({ claim:action, evidence:[ev()], self_check:selfCheck() }, now);
    expect(r.classification).toBe("UNKNOWN");
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("action_final_state_boundary_required");
  });

  it("guard_claim fails closed on caller-only post-action timestamps", () => {
    const action = claim({kind:"action_state",after:"2026-09-27T16:29:50Z"});
    const r = guardClaim({ claim:action, evidence:[ev()], self_check:selfCheck() }, now);
    expect(r.stage).toBe("verification");
    expect(r.approved).toBe(false);
    expect(r.classification).toBe("UNKNOWN");
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("trusted_post_action_evidence_required");
  });

  it("guard_claim escalates high-risk fact without human approval", () => {
    const risky = claim({risk:"high"});
    const r = guardClaim({ claim:risky, evidence:[ev()], self_check:selfCheck(), human_approved:false }, now);
    expect(r.classification).toBe("FACT");
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("human_approval_required");
  });

  it("guard_claim fail-closes high-risk even when caller asserts human approval", () => {
    const risky = claim({risk:"high"});
    const r = guardClaim({ claim:risky, evidence:[ev()], self_check:selfCheck(), human_approved:true }, now);
    expect(r.classification).toBe("FACT");
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("verified_human_approval_unavailable");
    expect(r.human_approval.mode).toBe("fail_closed");
    expect(r.human_approval.caller_asserted).toBe(true);
    expect(r.human_approval.verified).toBe(false);
  });


  it("rejects duplicate source references in a bounded claim", () => {
    const c = claim({ sources:[{type:"supplied",id:"health"},{type:"supplied",id:"health"}] });
    const r = verifyClaims([c],[ev()],now);
    expect(r.status).toBe("BLOCK");
    expect(r.reason).toBe("invalid_input");
  });

  it("collapses identical supplied document aliases in receipt counts", () => {
    const c = claim({ sources:[{type:"supplied",id:"alias-a"},{type:"supplied",id:"alias-b"}] });
    const e1 = { id:"alias-a", data:{status:"ok",payload:{x:1}}, observed_at:ts };
    const e2 = { id:"alias-b", data:{payload:{x:1},status:"ok"}, observed_at:ts };
    const r = verifyClaims([c],[e1,e2],now);
    expect(r.approved).toBe(true);
    expect(r.claims[0].contradiction_check.supporting).toBe(1);
  });

  it("guard_claim fails closed for action_state with caller-only timestamp evidence", () => {
    const action = claim({kind:"action_state",after:"2026-09-27T16:29:50Z"});
    const r = guardClaim({ claim:action, evidence:[ev()], self_check:selfCheck() }, now);
    expect(r.approved).toBe(false);
    expect(r.status).toBe("ESCALATE");
    expect(r.reason).toBe("trusted_post_action_evidence_required");
  });

  it("health advertises fail-closed remote human approval mode", () => {
    const h:any = health(now);
    expect(h.human_approval_mode).toBe("fail_closed_unverified_remote");
  });
});
