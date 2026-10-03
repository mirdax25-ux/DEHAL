export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue };

export const SERVER_VERSION = "1.2.0-rc.3";
export const CORE_VERSION = "2.0.0-compatible";
export const CORE_DIGEST = "floot-ts-guard-loop-1.2.0-rc.3-20261003";
export const GUARD_VERSION = "2.0.0";
export const HUMAN_APPROVAL_MODE = "fail_closed_unverified_remote";
export const SCOPE = "Supplied evidence content only. Source authority, independence, authenticity, caller timestamps, real-world truth and external system state are UNVERIFIED. Approval never certifies a free-text completion claim.";
export const MAX_CANONICAL_TOOL_INPUT_BYTES = 128 * 1024;
export const MAX_JSON_DEPTH = 16;

function canonicalJson(value: any): string | null {
  try {
    const encode = (v: any): string => {
      if (v === null || typeof v === "boolean" || typeof v === "string") return JSON.stringify(v);
      if (typeof v === "number") {
        if (!Number.isFinite(v)) throw new Error("non-finite number");
        return JSON.stringify(v);
      }
      if (Array.isArray(v)) return "[" + v.map(encode).join(",") + "]";
      if (v && typeof v === "object") {
        return "{" + Object.keys(v).sort().map(k => JSON.stringify(k) + ":" + encode(v[k])).join(",") + "}";
      }
      throw new Error("unsupported JSON value");
    };
    return encode(value);
  } catch {
    return null;
  }
}

export function canonicalJsonByteLength(value: any): number | null {
  const encoded = canonicalJson(value);
  return encoded === null ? null : new TextEncoder().encode(encoded).byteLength;
}

export function jsonDepth(value: any): number {
  if (value === null || typeof value !== "object") return 0;
  const children = Array.isArray(value) ? value : Object.values(value);
  return 1 + (children.length ? Math.max(...children.map(jsonDepth)) : 0);
}

function remoteInputWithinLimits(value: any): boolean {
  const bytes = canonicalJsonByteLength(value);
  return bytes !== null && bytes <= MAX_CANONICAL_TOOL_INPUT_BYTES && jsonDepth(value) <= MAX_JSON_DEPTH;
}

function parseTime(value: unknown): number | null {
  if (typeof value !== "string") return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,9}))?(Z|[+-]\d{2}:\d{2})$/);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const hour = Number(match[4]);
  const minute = Number(match[5]);
  const second = Number(match[6]);
  if (month < 1 || month > 12 || hour > 23 || minute > 59 || second > 59) return null;
  const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
  const daysInMonth = [0, 31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
  if (day < 1 || day > daysInMonth[month]) return null;
  const zone = match[8];
  if (zone !== "Z") {
    const zoneHour = Number(zone.slice(1, 3));
    const zoneMinute = Number(zone.slice(4, 6));
    if (zoneHour > 23 || zoneMinute > 59) return null;
  }
  const t = Date.parse(value);
  return Number.isFinite(t) ? t : null;
}

function strictEqual(a: JsonValue, b: JsonValue): boolean {
  if (Array.isArray(a) || Array.isArray(b)) {
    if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) return false;
    return a.every((v, i) => strictEqual(v, b[i]));
  }
  if (a && typeof a === "object" || b && typeof b === "object") {
    if (!a || !b || typeof a !== "object" || typeof b !== "object" || Array.isArray(a) || Array.isArray(b)) return false;
    const ak = Object.keys(a), bk = Object.keys(b);
    return ak.length === bk.length && ak.every(k => Object.prototype.hasOwnProperty.call(b, k) && strictEqual(a[k], b[k]));
  }
  return typeof a === typeof b && Object.is(a, b);
}

function pointer(data: JsonValue, ptr: string): JsonValue | undefined {
  if (ptr === "") return data;
  if (!ptr.startsWith("/")) return undefined;
  let current: any = data;
  for (const raw of ptr.slice(1).split("/")) {
    const key = raw.replace(/~1/g, "/").replace(/~0/g, "~");
    if (Array.isArray(current)) {
      if (!/^(0|[1-9][0-9]*)$/.test(key)) return undefined;
      current = current[Number(key)];
    } else if (current && typeof current === "object" && Object.prototype.hasOwnProperty.call(current, key)) {
      current = current[key];
    } else return undefined;
  }
  return current as JsonValue;
}

function invalid() {
  return { version: SERVER_VERSION, classification: "UNKNOWN", approved: false, status: "BLOCK", reason: "invalid_input", scope: SCOPE, claims: [] };
}

export function health(now = new Date()) {
  return {
    status: "ok", version: SERVER_VERSION, core_version: CORE_VERSION, core_sha256: CORE_DIGEST,
    observed_at: now.toISOString(), transport: "streamable-http", authentication: "none",
    evidence_mode: "supplied_json_only", max_claims: 20,
    rate_limit: "platform-managed", claim_verification_scope: "bounded supplied JSON predicates only",
    human_approval_mode: HUMAN_APPROVAL_MODE
  };
}

export function verifyClaims(claims: any, evidence: any, now = new Date()) {
  if (!remoteInputWithinLimits({ claims, evidence })) return invalid();
  if (!Array.isArray(claims) || claims.length < 1 || claims.length > 20 || !Array.isArray(evidence) || evidence.length > 40) return invalid();
  const evidenceMap = new Map<string, any>();
  for (const item of evidence) {
    if (!item || typeof item !== "object" || typeof item.id !== "string" || evidenceMap.has(item.id) || !("data" in item) || parseTime(item.observed_at) === null) return invalid();
    evidenceMap.set(item.id, item);
  }
  const rows: any[] = [];
  const claimIds = new Set<string>();
  for (let i = 0; i < claims.length; i++) {
    const c = claims[i];
    if (!c || typeof c !== "object" || typeof c.id !== "string" || typeof c.kind !== "string" || claimIds.has(c.id)) return invalid();
    claimIds.add(c.id);
    if ("risk" in c) return invalid();
    if (c.kind === "text") {
      if (Object.keys(c).sort().join(",") !== "id,kind,text" || typeof c.text !== "string" || !c.text.trim()) return invalid();
      rows.push({ claim_index: i, classification: "UNKNOWN", approved: false, status: "BLOCK", reason: "Free text requires semantic verification against authoritative sources; this engine cannot certify it.", bounded_claim: "Free text is not certified.", evidence: [], contradiction_check: {} });
      continue;
    }
    if (c.kind === "observation" && ("text" in c || "rationale" in c || "assumptions" in c)) return invalid();
    if (!["observation","inference","estimate"].includes(c.kind)) return invalid();
    const a = c.assertion;
    if (!a || a.op !== "json_equals" || typeof a.pointer !== "string" || !Array.isArray(c.sources) || c.sources.length < 1 || c.sources.length > 10) return invalid();
    if (c.sources.some((s:any) => !s || s.type !== "supplied" || typeof s.id !== "string" || Object.keys(s).sort().join(",") !== "id,type")) return invalid();
    const maxAge = c.max_age_seconds ?? 300;
    if (typeof maxAge !== "number" || maxAge < 1 || maxAge > 86400) return invalid();
    const after = "after" in c ? parseTime(c.after) : null;
    if ("after" in c && after === null) return invalid();
    const evs = c.sources.map((s:any, sourceIndex:number) => {
      const item = evidenceMap.get(s.id);
      const observed = item ? parseTime(item.observed_at) : null;
      const selected = item ? pointer(item.data as JsonValue, a.pointer) : undefined;
      const matched = selected === undefined ? null : strictEqual(selected, a.expected as JsonValue);
      const fresh = observed !== null && observed <= now.getTime() && now.getTime() - observed <= maxAge * 1000;
      const postAction = observed !== null && (after === null || observed >= after);
      return { source_index: sourceIndex, directness: "supplied_document_read", observed_at: now.toISOString(), content_observed_at: observed === null ? undefined : new Date(observed).toISOString(), matched, fresh, post_action: postAction, eligible: fresh && postAction && matched !== null };
    });
    const eligible = evs.filter((e: any) => e.eligible);
    const supporting = eligible.filter((e: any) => e.matched === true).length;
    const contradicting = eligible.filter((e: any) => e.matched === false).length;
    const cc = { supporting, contradicting, unavailable_or_stale: evs.length - eligible.length };
    let classification = "UNKNOWN", approved = false, status = "BLOCK", reason = "Evidence is missing, stale, invalid, or predates the action.";
    if (supporting > 0 && contradicting > 0) { classification = "CONFLICT"; reason = "Fresh direct observations disagree on the supplied predicate; source identity/authority needs review."; }
    else if (contradicting > 0) reason = "Direct counterevidence contradicts the requested predicate. The requested claim is not approved.";
    else if (eligible.length === evs.length && c.kind === "observation") { classification = "FACT"; approved = true; status = "APPROVE"; reason = "All supplied sources directly satisfy this bounded predicate at the recorded observation times."; }
    else if (eligible.length === evs.length) classification = c.kind.toUpperCase();
    rows.push({ claim_index:i, classification, approved, status, reason, bounded_claim:"The selected value in the supplied JSON equals the requested value, including its type.", evidence:evs, contradiction_check:cc });
  }
  const approved = rows.every(r => r.approved);
  const classes = rows.map(r => r.classification);
  const classification = approved ? "FACT" : classes.includes("CONFLICT") ? "CONFLICT" : classes.includes("UNKNOWN") ? "UNKNOWN" : classes.includes("ESTIMATE") ? "ESTIMATE" : "INFERENCE";
  return { version: SERVER_VERSION, core_version: CORE_VERSION, approved, status: approved ? "APPROVE" : "BLOCK", classification, reason: approved ? "bounded_predicates_approved" : "one_or_more_claims_blocked", scope: SCOPE, checked_at: now.toISOString(), claims: rows };
}

function validStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === "string" && item.trim().length > 0);
}

function guardPrecheckResult(selfCheck: any, status: "BLOCK" | "ESCALATE", reason: string, now: Date) {
  return {
    version: SERVER_VERSION,
    core_version: CORE_VERSION,
    guard_version: GUARD_VERSION,
    stage: "self_check",
    approved: false,
    classification: "UNKNOWN",
    status,
    reason,
    scope: SCOPE,
    checked_at: now.toISOString(),
    self_check: selfCheck,
    verification: null,
  };
}

export function guardClaim(input: any, now = new Date()): any {
  if (!remoteInputWithinLimits(input) || !input || typeof input !== "object") return invalid();

  const claim = input.claim;
  const evidence = input.evidence;
  const selfCheck = input.self_check;
  const humanApproved = input.human_approved ?? false;

  if (!claim || typeof claim !== "object" || !Array.isArray(evidence) || !selfCheck || typeof selfCheck !== "object") return invalid();
  if (typeof humanApproved !== "boolean") return invalid();
  if (!["possible", "uncertain", "impossible"].includes(selfCheck.realism)) return invalid();
  if (!validStringArray(selfCheck.known) || !validStringArray(selfCheck.assumptions) || !validStringArray(selfCheck.unknowns)) return invalid();
  if (typeof selfCheck.assumptions_reviewed !== "boolean" || typeof selfCheck.unknowns_reviewed !== "boolean") return invalid();

  if (selfCheck.realism === "impossible") return guardPrecheckResult(selfCheck, "BLOCK", "self_check_impossible", now);
  if (selfCheck.realism === "uncertain") return guardPrecheckResult(selfCheck, "ESCALATE", "self_check_uncertain", now);
  if (!selfCheck.assumptions_reviewed) return guardPrecheckResult(selfCheck, "ESCALATE", "assumptions_not_reviewed", now);
  if (!selfCheck.unknowns_reviewed) return guardPrecheckResult(selfCheck, "ESCALATE", "unknowns_not_reviewed", now);

  const risk = claim.risk ?? "low";
  if (!["low", "high"].includes(risk)) return invalid();

  let boundedClaim: any;
  if (claim.kind === "action_state") {
    if (!("after" in claim) || parseTime(claim.after) === null) {
      return {
        version: SERVER_VERSION,
        core_version: CORE_VERSION,
        guard_version: GUARD_VERSION,
        stage: "verification",
        approved: false,
        classification: "UNKNOWN",
        status: "BLOCK",
        reason: "action_final_state_boundary_required",
        scope: SCOPE,
        checked_at: now.toISOString(),
        self_check: selfCheck,
        verification: null,
      };
    }
    boundedClaim = { ...claim, kind: "observation" };
  } else {
    boundedClaim = { ...claim };
  }
  delete boundedClaim.risk;

  const verification = verifyClaims([boundedClaim], evidence, now);
  const claimReason = verification?.claims?.[0]?.reason ?? verification.reason;

  if (verification.approved && risk === "high") {
    const callerAsserted = humanApproved === true;
    return {
      version: SERVER_VERSION,
      core_version: CORE_VERSION,
      guard_version: GUARD_VERSION,
      stage: "verification",
      approved: false,
      classification: "FACT",
      status: "ESCALATE",
      reason: callerAsserted ? "verified_human_approval_unavailable" : "human_approval_required",
      scope: SCOPE,
      checked_at: now.toISOString(),
      self_check: selfCheck,
      human_approval: {
        mode: "fail_closed",
        caller_asserted: callerAsserted,
        verified: false,
      },
      verification,
    };
  }

  return {
    version: SERVER_VERSION,
    core_version: CORE_VERSION,
    guard_version: GUARD_VERSION,
    stage: "verification",
    approved: verification.approved,
    classification: verification.classification,
    status: verification.status,
    reason: claimReason,
    scope: SCOPE,
    checked_at: now.toISOString(),
    self_check: selfCheck,
    verification,
  };
}

export function verifyManifest(manifest: any, evidence: any, now = new Date()) {
  if (!remoteInputWithinLimits({ manifest, evidence })) return invalid();
  if (!manifest || typeof manifest !== "object" || manifest.schema_version !== 1 || !Array.isArray(manifest.claims)) return invalid();
  return verifyClaims(manifest.claims, evidence, now);
}
