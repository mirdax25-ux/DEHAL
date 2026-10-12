import { createProtectedHalServer } from "./server.js";
import { smokeTest } from "./smoke.js";
import { configFromEnvironment, OAuthVerifier } from "./oauth.js";

const secret = process.env.BODULHAL_STAGING_TOKEN ?? "";
const port = Number(process.env.PORT ?? "10000");
if (!Number.isSafeInteger(port) || port < 1 || port > 65535) {
  throw new Error("Invalid PORT");
}
const oauthConfig = configFromEnvironment();
const oauthVerifier = oauthConfig ? new OAuthVerifier(oauthConfig) : null;
const server = createProtectedHalServer(secret, oauthVerifier);
server.listen(port, "0.0.0.0", () => {
  console.log("BodulHal protected staging listening on port " + port);
  void smokeTest(port, secret);
});
