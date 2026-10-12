import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createProtectedHalServer } from "../dist/server.js";
import { SERVER_VERSION, CORE_DIGEST, verifyClaims } from "../dist/BodulHalCore.js";

const SECRET = "test-only-DO-NOT-DEPLOY-BodulAI-secret-67890";
const rpc = (method, params = {}, id = 1) =>
  ({ jsonrpc: "2.0", id, method, params });

async function withServer(fn) {
  const srv = createProtectedHalServer(SECRET);
  srv.listen(0, "127.0.0.1");
  await once(srv, "listening");
  const address = srv.address();
  const base = "http://127.0.0.1:" + address.port;
  try { await fn(base); }
  finally { await new Promise((resolve, reject) => srv.close(err => err ? reject(err) : resolve())); }
}
const request = (url, body, auth = true) =>
  fetch(url + "/mcp", {
    method: "POST",
    headers: { "Content-Type": "application/json", ...(auth ? { Authorization: "Bearer " + SECRET } : {}) },
    body: JSON.stringify(body),
  });

test("same exact Floot rc.4 version fingerprint", () => {
  assert.equal(SERVER_VERSION, "1.2.0-rc.4");
  assert.equal(CORE_DIGEST, "floot-ts-guard-loop-1.2.0-rc.4-20261007");
});

test("missing or short secret cannot start", () => {
  assert.throws(() => createProtectedHalServer(""), /required/);
  assert.throws(() => createProtectedHalServer("short"), /required/);
});

test("health response preserves core identity and discloses staging authorization", async () => {
  await withServer(async base => {
    const res = await fetch(base + "/health");
    assert.equal(res.status, 200);
    const data = await res.json();
    assert.equal(data.version, SERVER_VERSION);
    assert.equal(data.core_sha256, CORE_DIGEST);
    assert.equal(data.authentication, "staging-bearer");
  });
});

test("unauthenticated RPC fails closed", async () => {
  await withServer(async base => {
    for (const token of [undefined, "Bearer wrong"]) {
      const res = await fetch(base + "/mcp", {
        method: "POST",
        headers: {"Content-Type": "application/json", ...(token ? {Authorization:token} : {})},
        body: JSON.stringify(rpc("tools/list")),
      });
      assert.equal(res.status, 401);
      assert.equal((await res.json()).error, "authentication_required");
    }
  });
});

test("authentic MCP initialize and tools/list preserve four tools", async () => {
  await withServer(async base => {
    const init = await request(base, rpc("initialize", { protocolVersion:"2025-06-18", capabilities:{}, clientInfo:{name:"parity-test",version:"1"} }));
    assert.equal(init.status, 200);
    const initJson = await init.json();
    assert.equal(initJson.result.serverInfo.version, SERVER_VERSION);
    const list = await request(base, rpc("tools/list"));
    assert.equal(list.status, 200);
    const j = await list.json();
    assert.deepEqual(j.result.tools.map(t => t.name), ["health","verify_claims","verify_manifest","guard_claim"]);
  });
});

test("parity: positive FACT and type-mismatch BLOCK", async () => {
  await withServer(async base => {
    const stamp = new Date().toISOString();
    const evidence = [{id:"e1",data:{flag:true},observed_at:stamp}];
    for (const [expected, shouldApprove] of [[true,true],[1,false]]) {
      const claims = [{id:"x",kind:"observation",assertion:{op:"json_equals",pointer:"/flag",expected},sources:[{type:"supplied",id:"e1"}],max_age_seconds:300}];
      const local = verifyClaims(claims, evidence);
      const remote = await request(base,rpc("tools/call",{name:"verify_claims",arguments:{claims,evidence}}));
      assert.equal(remote.status,200);
      const j = await remote.json();
      assert.equal(j.result.structuredContent.status,local.status);
      assert.equal(j.result.structuredContent.approved,shouldApprove);
    }
  });
});

test("unauthenticated GET blocked, authenticated GET is 405", async () => {
  await withServer(async base => {
    assert.equal((await fetch(base+"/mcp")).status,401);
    assert.equal((await fetch(base+"/mcp",{headers:{Authorization:"Bearer "+SECRET}})).status,405);
  });
});

test("invalid JSON doesn't succeed", async () => {
  await withServer(async base => {
    const res = await fetch(base+"/mcp", {method:"POST",headers:{Authorization:"Bearer "+SECRET},body:"{bad-json"});
    assert.equal(res.status,400);
  });
});

test("unknown routes do not expose server", async () => {
  await withServer(async base => {
    assert.equal((await fetch(base+"/admin")).status,404);
  });
});
