/** OAuth 2.1 resource-server guard for the isolated BodulHal staging route.
 *
 * The existing bearer-only Floot parity route is not affected. No broad
 * 'authenticated' Supabase audience fallback is allowed. OAuth enablement
 * requires explicit per-resource audience and OAuth-client allowlist.
 */
import { createRemoteJWKSet, jwtVerify, type JWTVerifyGetKey, type JWTPayload } from "jose";

export const OAUTH_RESOURCE = "https://brutala-hal.onrender.com/oauth/mcp";
export const OAUTH_ISSUER = "https://xqoxcqkpzweclpqliqwn.supabase.co/auth/v1";
export const OAUTH_JWKS = OAUTH_ISSUER + "/.well-known/jwks.json";
export const OAUTH_METADATA_PATH = "/.well-known/oauth-protected-resource/oauth/mcp";
export const OAUTH_METADATA_URL = "https://brutala-hal.onrender.com" + OAUTH_METADATA_PATH;

const CLIENT_ID_PATTERN = /^[A-Za-z0-9_-]{8,128}$/;
const ALGORITHMS = ["RS256", "ES256"];

export type OAuthConfig = {
  allowedClientIds: readonly string[];
  resource: string;
  issuer: string;
};

export class OAuthTokenDenied extends Error {
  constructor() { super("oauth_access_denied"); this.name = "OAuthTokenDenied"; }
}

export function configFromEnvironment(env: NodeJS.ProcessEnv = process.env): OAuthConfig | null {
  const raw = env.BODULHAL_OAUTH_ALLOWED_CLIENT_IDS;
  if (!raw || !raw.trim()) return null;
  const ids = raw.split(",").map(x => x.trim());
  if (!ids.length || ids.length > 16 || ids.some(x => !CLIENT_ID_PATTERN.test(x)) ||
      new Set(ids).size !== ids.length) {
    throw new Error("Invalid BODULHAL_OAUTH_ALLOWED_CLIENT_IDS; refuse to enable OAuth");
  }
  return { allowedClientIds: ids, resource: OAUTH_RESOURCE, issuer: OAUTH_ISSUER };
}

export function protectedResourceMetadata(config: OAuthConfig) {
  return {
    resource: config.resource,
    authorization_servers: [config.issuer],
    bearer_methods_supported: ["header"],
  };
}

export function oauthChallenge(): string {
  return 'Bearer resource_metadata="' + OAUTH_METADATA_URL + '"';
}

export class OAuthVerifier {
  private readonly resolver: JWTVerifyGetKey;
  get configuration(): OAuthConfig { return this.config; }
  constructor(private readonly config: OAuthConfig, localResolver?: JWTVerifyGetKey) {
    if (config.issuer !== OAUTH_ISSUER || config.resource !== OAUTH_RESOURCE ||
        !config.allowedClientIds.length ||
        config.allowedClientIds.some(id => !CLIENT_ID_PATTERN.test(id))) {
      throw new Error("Invalid, missing, or unpinned OAuth configuration");
    }
    this.resolver = localResolver ?? createRemoteJWKSet(new URL(OAUTH_JWKS), {
      cooldownDuration: 30000,
      cacheMaxAge: 300000,
      timeoutDuration: 5000,
    });
  }

  async verify(authorization: string | undefined): Promise<{ userId: string; clientId: string }> {
    if (!authorization || !/^Bearer [^\s]+$/.test(authorization) ||
        authorization.length > 8199) throw new OAuthTokenDenied();
    const token = authorization.slice(7);
    try {
      const { payload, protectedHeader } = await jwtVerify(token, this.resolver, {
        algorithms: ALGORITHMS,
        issuer: this.config.issuer,
        audience: this.config.resource,
        clockTolerance: 15,
        requiredClaims: ["exp", "iat", "iss", "aud", "sub"],
      });
      if (!ALGORITHMS.includes(protectedHeader.alg)) throw new OAuthTokenDenied();
      // Prevent accepting a general-use Supabase token or multi-audience token.
      if (payload.aud !== this.config.resource) throw new OAuthTokenDenied();
      if (!Number.isInteger(payload.iat) || !Number.isInteger(payload.exp) ||
          payload.iat! > Math.floor(Date.now() / 1000) + 15) throw new OAuthTokenDenied();
      if (typeof payload.sub !== "string" || payload.sub.length < 8 || payload.sub.length > 128)
        throw new OAuthTokenDenied();
      const clientId = (payload as JWTPayload & {client_id?: unknown}).client_id;
      if (typeof clientId !== "string" || !this.config.allowedClientIds.includes(clientId))
        throw new OAuthTokenDenied();
      if (payload.role !== "authenticated" ||
          typeof payload.session_id !== "string" || payload.session_id.length < 8)
        throw new OAuthTokenDenied();
      return {userId:payload.sub, clientId};
    } catch {
      // Never leak claims, signatures, bearer headers, JWKS details or user IDs.
      throw new OAuthTokenDenied();
    }
  }
}
