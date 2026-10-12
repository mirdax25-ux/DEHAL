import { createProtectedHalServer } from "./server.js";

const secret = process.env.BODULHAL_STAGING_TOKEN ?? "";
const port = Number(process.env.PORT ?? "10000");
if (!Number.isSafeInteger(port) || port < 1 || port > 65535) {
  throw new Error("Invalid PORT");
}
const server = createProtectedHalServer(secret);
server.listen(port, "0.0.0.0", () => {
  console.log("BodulHal protected staging listening on port " + port);
});
