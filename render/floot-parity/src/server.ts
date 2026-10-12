/** Protected Render staging adapter for exact Floot BodulHal rc.4 MCP logic.
 * Existing Floot endpoint remains untouched. This service fails closed if no
 * sufficiently long staging secret is configured. Never log the secret.
 */
import { timingSafeEqual } from "node:crypto";
import { createServer, type IncomingMessage, type ServerResponse } from "node:http";
import { health } from "./BodulHalCore.js";
import { handle as flootMcpHandler } from "./mcp_floot.js";
import { OAuthVerifier, OAUTH_METADATA_PATH, oauthChallenge, protectedResourceMetadata } from "./oauth.js";

const MAX_BODY = 256 * 1024;

function respond(res: ServerResponse, status: number, payload: unknown, extra: Record<string, string> = {}): void {
  res.writeHead(status, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
    ...extra,
  });
  res.end(JSON.stringify(payload));
}

function authorized(header: string | undefined, secret: string): boolean {
  const provided = Buffer.from(header ?? "", "utf8");
  const expected = Buffer.from("Bearer " + secret, "utf8");
  return provided.length === expected.length && timingSafeEqual(provided, expected);
}

async function readBoundedBody(req: IncomingMessage): Promise<Buffer | null> {
  const chunks: Buffer[] = [];
  let size = 0;
  for await (const chunk of req) {
    const buffer = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
    size += buffer.length;
    if (size > MAX_BODY) return null;
    chunks.push(buffer);
  }
  return Buffer.concat(chunks);
}

export function createProtectedHalServer(secret: string, oauthVerifier: OAuthVerifier | null = null) {
  if (typeof secret !== "string" || secret.length < 32) {
    throw new Error("BODULHAL_STAGING_TOKEN (minimum 32 characters) is required");
  }

  return createServer(async (req, res) => {
    const url = (req.url ?? "").split("?")[0];
    if (req.method === "GET" && url === "/health") {
      // Core fingerprint stays original; deployment authentication is accurate.
      respond(res, 200, { ...health(), authentication: "staging-bearer", deployment: "render-protected-staging", oauth_endpoint: oauthVerifier ? "configured" : "disabled" });
      return;
    }
    if (url === OAUTH_METADATA_PATH) {
      if (!oauthVerifier) {
        respond(res, 404, { error: "not_found" });
        return;
      }
      if (req.method !== "GET") {
        respond(res, 405, { error: "method_not_allowed" }, { "Allow": "GET" });
        return;
      }
      respond(res, 200, protectedResourceMetadata(oauthVerifier.configuration));
      return;
    }

    const oauthRoute = url === "/oauth/mcp";
    const stagingRoute = url === "/mcp" || url === "/_api/mcp";
    if (!oauthRoute && !stagingRoute) {
      respond(res, 404, { error: "not_found" });
      return;
    }
    if (oauthRoute) {
      // A missing client allowlist disables the endpoint entirely.
      if (!oauthVerifier) {
        respond(res, 404, { error: "not_found" });
        return;
      }
      try {
        await oauthVerifier.verify(req.headers.authorization);
      } catch {
        respond(res, 401, { error: "authentication_required" },
          { "WWW-Authenticate": oauthChallenge() });
        return;
      }
    } else if (!authorized(req.headers.authorization, secret)) {
      // Old staging bearer is never accepted on /oauth/mcp.
      respond(res, 401, { error: "authentication_required" }, { "WWW-Authenticate": 'Bearer realm="BodulHal staging"' });
      return;
    }
    if (req.method !== "POST") {
      respond(res, 405, { error: "method_not_allowed" }, { "Allow": "POST" });
      return;
    }

    try {
      const bytes = await readBoundedBody(req);
      if (!bytes) {
        respond(res, 413, { error: "request_body_too_large" });
        return;
      }
      const request = new Request("http://127.0.0.1/_api/mcp", {
        method: "POST",
        headers: { "content-type": req.headers["content-type"] ?? "application/json" },
        body: bytes.toString("utf8"),
      });
      const response = await flootMcpHandler(request);
      // Preserve JSON-RPC success/error semantics from the original Floot handler.
      const payload = Buffer.from(await response.arrayBuffer());
      res.writeHead(response.status, {
        "Content-Type": response.headers.get("content-type") ?? "application/json",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      });
      res.end(payload);
    } catch {
      // No details, headers, tokens, stack traces, or user evidence in HTTP errors.
      respond(res, 500, { error: "internal_error" });
    }
  });
}
