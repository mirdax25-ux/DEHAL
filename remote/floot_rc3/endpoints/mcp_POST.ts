import { SERVER_VERSION, guardClaim, health, verifyClaims, verifyManifest } from "../helpers/B.1.2Core";

type Rpc = { jsonrpc?: string; id?: string | number | null; method?: string; params?: any };
const MAX_HTTP_BODY_BYTES = 256 * 1024;
const SUPPORTED_PROTOCOL_VERSION = "2025-06-18";

const toolDescriptors = [
  {
    name: "health",
    description: "Return verifier service version, current UTC time, core identity and verification boundaries. Health does not prove a user's claim.",
    inputSchema: { type: "object", properties: {}, additionalProperties: false },
  },
  {
    name: "verify_claims",
    description: "Check bounded claims against supplied JSON evidence; return FACT/INFERENCE/ESTIMATE/UNKNOWN/CONFLICT and APPROVE/BLOCK.",
    inputSchema: {
      type: "object",
      properties: { claims: { type: "array" }, evidence: { type: "array" } },
      required: ["claims", "evidence"],
      additionalProperties: false,
    },
  },
  {
    name: "verify_manifest",
    description: "Apply evidence-contract v1 to a remote-safe manifest containing bounded supplied-JSON predicates.",
    inputSchema: {
      type: "object",
      properties: { manifest: { type: "object" }, evidence: { type: "array" } },
      required: ["manifest", "evidence"],
      additionalProperties: false,
    },
  },
  {
    name: "guard_claim",
    description: "Run the B.1.2 AI Guard Loop: mandatory self-check first, then bounded evidence verification and final-state enforcement. High-risk remote claims always fail closed to ESCALATE because human approval is not authenticated on this transport.",
    inputSchema: {
      type: "object",
      properties: {
        claim: { type: "object" },
        evidence: { type: "array" },
        self_check: {
          type: "object",
          properties: {
            realism: { type: "string", enum: ["possible", "uncertain", "impossible"] },
            known: { type: "array", items: { type: "string" } },
            assumptions: { type: "array", items: { type: "string" } },
            unknowns: { type: "array", items: { type: "string" } },
            assumptions_reviewed: { type: "boolean" },
            unknowns_reviewed: { type: "boolean" },
          },
          required: ["realism", "known", "assumptions", "unknowns", "assumptions_reviewed", "unknowns_reviewed"],
          additionalProperties: false,
        },
        human_approved: { type: "boolean" },
      },
      required: ["claim", "evidence", "self_check"],
      additionalProperties: false,
    },
  },
];

function success(id: Rpc["id"], result: any) {
  return { jsonrpc: "2.0", id: id ?? null, result };
}

function failure(id: Rpc["id"], code: number, message: string) {
  return { jsonrpc: "2.0", id: id ?? null, error: { code, message } };
}

function toolPayload(value: any) {
  return { content: [{ type: "text", text: JSON.stringify(value, null, 2) }], structuredContent: value };
}

async function readBodyWithinLimit(request: Request): Promise<string | null> {
  const contentLength = request.headers.get("content-length");
  if (contentLength !== null) {
    const declared = Number(contentLength);
    if (Number.isFinite(declared) && declared > MAX_HTTP_BODY_BYTES) return null;
  }
  if (!request.body) return "";
  const reader = request.body.getReader();
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      total += value.byteLength;
      if (total > MAX_HTTP_BODY_BYTES) {
        try { await reader.cancel(); } catch {}
        return null;
      }
      chunks.push(value);
    }
  } finally {
    reader.releaseLock();
  }
  const body = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    body.set(chunk, offset);
    offset += chunk.byteLength;
  }
  return new TextDecoder().decode(body);
}

function dispatch(message: Rpc): any {
  const id = message?.id;
  if (!message || message.jsonrpc !== "2.0" || typeof message.method !== "string") return failure(id, -32600, "Invalid Request");
  if (message.method === "initialize") {
    const requested = message.params?.protocolVersion;
    return success(id, {
      protocolVersion: requested === SUPPORTED_PROTOCOL_VERSION ? requested : SUPPORTED_PROTOCOL_VERSION,
      capabilities: { tools: { listChanged: false } },
      serverInfo: { name: "B.1.2", version: SERVER_VERSION },
    });
  }
  if (message.method === "ping") return success(id, {});
  if (message.method === "tools/list") return success(id, { tools: toolDescriptors });
  if (message.method === "tools/call") {
    const name = message.params?.name;
    const args = message.params?.arguments ?? {};
    if (name === "health") return success(id, toolPayload(health()));
    if (name === "verify_claims") return success(id, toolPayload(verifyClaims(args.claims, args.evidence)));
    if (name === "verify_manifest") return success(id, toolPayload(verifyManifest(args.manifest, args.evidence)));
    if (name === "guard_claim") return success(id, toolPayload(guardClaim(args)));
    return failure(id, -32602, "Unknown tool");
  }
  if (message.method.startsWith("notifications/")) return null;
  return failure(id, -32601, "Method not found");
}

export async function handle(request: Request) {
  try {
    const body = await readBodyWithinLimit(request);
    if (body === null) {
      return new Response(JSON.stringify(failure(null, -32600, "Request body too large")), {
        status: 413,
        headers: { "Content-Type": "application/json", "Cache-Control": "no-store" },
      });
    }
    const message = JSON.parse(body);
    if (Array.isArray(message)) {
      const replies = message.map(dispatch).filter(Boolean);
      return new Response(JSON.stringify(replies), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
    }
    const reply = dispatch(message);
    if (reply === null) return new Response("accepted", { status: 202, headers: { "Content-Type": "text/plain", "Cache-Control": "no-store" } });
    return new Response(JSON.stringify(reply), { status: 200, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  } catch {
    return new Response(JSON.stringify(failure(null, -32700, "Parse error")), { status: 400, headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } });
  }
}
