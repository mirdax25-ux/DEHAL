import test from "node:test";
import assert from "node:assert/strict";
import { once } from "node:events";
import { createLocalJWKSet, exportJWK, generateKeyPair, SignJWT } from "jose";
import { createProtectedHalServer } from "../dist/server.js";
import { OAuthVerifier, OAuthTokenDenied, OAUTH_ISSUER, OAUTH_RESOURCE, OAUTH_METADATA_PATH,
  configFromEnvironment } from "../dist/oauth.js";

const SECRET = "test-only-staging-bearer-no-real-credentials-1234";
const CLIENT = "registered-client-1234";
const USER = "00000000-0000-4000-8000-000000000001";
const SESSION = "00000000-0000-4000-8000-000000000002";
const CONFIG = Object.freeze({issuer:OAUTH_ISSUER,resource:OAUTH_RESOURCE,allowedClientIds:[CLIENT]});

const { publicKey, privateKey } = await generateKeyPair("RS256");
const exported = await exportJWK(publicKey);
const keys = createLocalJWKSet({keys:[{...exported, kid:"trusted-key", alg:"RS256",use:"sig"}]});
const other = await generateKeyPair("RS256");

const oauthVerifier = new OAuthVerifier(CONFIG, keys);
async function token(patch = {}, signer = privateKey) {
  let builder = new SignJWT({
    role: patch.role ?? "authenticated",
    client_id: patch.client_id ?? CLIENT,
    ...(patch.omitSession ? {} : {session_id:SESSION}),
  }).setProtectedHeader({alg:"RS256",kid:"trusted-key"})
    .setIssuer(patch.iss ?? OAUTH_ISSUER)
    .setAudience(patch.aud ?? OAUTH_RESOURCE)
    .setSubject(patch.sub ?? USER)
    .setIssuedAt(patch.iat ?? Math.floor(Date.now()/1000)-5)
    .setExpirationTime(patch.exp ?? Math.floor(Date.now()/1000)+300);
  return builder.sign(signer);
}
async function withServer(oauth, fn) {
  const server = createProtectedHalServer(SECRET,oauth);
  server.listen(0,"127.0.0.1");
  await once(server,"listening");
  try {
    const base = "http://127.0.0.1:"+server.address().port;
    await fn(base);
  } finally {
    await new Promise((resolve,reject)=>server.close(err=>err?reject(err):resolve()));
  }
}
function rpc(body = {jsonrpc:"2.0",id:1,method:"tools/list",params:{}}) {return JSON.stringify(body);}
const fetchOauth = (base,authorization) => fetch(base+"/oauth/mcp",{
  method:"POST",
  headers:{"Content-Type":"application/json",...(authorization?{"Authorization":authorization}:{})},
  body:rpc(),
});

test("OAuth disabled unless valid client allowlist is configured",()=>{
  assert.equal(configFromEnvironment({}),null);
  assert.equal(configFromEnvironment({BODULHAL_OAUTH_ALLOWED_CLIENT_IDS:""}),null);
  for(const bad of ["x","a,,b","client-id,client-id","client-id,evil/callback"]) {
    assert.throws(()=>configFromEnvironment({BODULHAL_OAUTH_ALLOWED_CLIENT_IDS:bad}),/Invalid/);
  }
  const conf=configFromEnvironment({BODULHAL_OAUTH_ALLOWED_CLIENT_IDS:CLIENT});
  assert.deepEqual(conf,CONFIG);
});

test("OAuth metadata is discoverable while unregistered clients remain blocked",async()=>{
  await withServer(null,async base=>{
    const noToken = await fetch(base+"/oauth/mcp");
    assert.equal(noToken.status,401);
    assert.match(noToken.headers.get("www-authenticate"),/resource_metadata=/);
    assert.equal((await fetchOauth(base,"Bearer "+SECRET)).status,401,
      "legacy bearer must never authenticate OAuth");
    const meta=await fetch(base+OAUTH_METADATA_PATH);
    assert.equal(meta.status,200);
    const body=await meta.json();
    assert.equal(body.resource,OAUTH_RESOURCE);
    assert.deepEqual(body.authorization_servers,[OAUTH_ISSUER]);
    assert.equal(Object.hasOwn(body,"client_secret"),false);
    const legacy=await fetch(base+"/mcp");assert.equal(legacy.status,401);
  });
});

test("OAuth 401 supplies RFC9728 resource metadata and no client credentials",async()=>{
  await withServer(oauthVerifier,async base=>{
    const denied=await fetchOauth(base);
    assert.equal(denied.status,401);
    assert.match(denied.headers.get("www-authenticate"),/resource_metadata="https:\/\/bodulhal-oauth-stage\.onrender\.com\/\.well-known\/oauth-protected-resource\/oauth\/mcp"/);
    const meta=await fetch(base+OAUTH_METADATA_PATH);
    assert.equal(meta.status,200);
    const json=await meta.json();
    assert.equal(json.resource,OAUTH_RESOURCE);
    assert.deepEqual(json.authorization_servers,[OAUTH_ISSUER]);
    assert.equal(Object.hasOwn(json,"client_secret"),false);
    assert.equal((await fetch(base+"/.well-known/oauth-protected-resource")).status,404);
  });
});

test("valid local test OAuth token reaches same four MCP tools",async()=>{
  await withServer(oauthVerifier,async base=>{
    const result=await fetchOauth(base,"Bearer "+await token());
    assert.equal(result.status,200);
    const json=await result.json();
    assert.deepEqual(json.result.tools.map(x=>x.name),["health","verify_claims","verify_manifest","guard_claim"]);
    assert.equal((await fetch(base+"/health").then(x=>x.json())).oauth_endpoint,"configured");
    const old=await fetch(base+"/mcp",{headers:{Authorization:"Bearer "+await token()}});
    assert.equal(old.status,401,"OAuth JWT must not become legacy staging bearer");
    const oauthUsingLegacy=await fetchOauth(base,"Bearer "+SECRET);
    assert.equal(oauthUsingLegacy.status,401,"Legacy bearer must not open OAuth route");
  });
});

test("wrong audience, client, issuer, role, signature, expiry or session denied",async()=>{
  const negatives=[
    ["general Supabase audience",{aud:"authenticated"}],
    ["different OAuth resource",{aud:"https://another.example/mcp"}],
    ["unlisted OAuth client",{client_id:"evil-client-1234"}],
    ["wrong issuer",{iss:"https://other.supabase.co/auth/v1"}],
    ["wrong role",{role:"anon"}],
    ["expired",{exp:Math.floor(Date.now()/1000)-80}],
    ["future issued",{iat:Math.floor(Date.now()/1000)+3600}],
    ["missing session",{omitSession:true}],
  ];
  for (const [label,opts] of negatives) {
    await assert.rejects(oauthVerifier.verify("Bearer "+await token(opts)),OAuthTokenDenied,label);
  }
  await assert.rejects(oauthVerifier.verify("Bearer "+await token({},other.privateKey)),OAuthTokenDenied,"untrusted signature");
  for (const value of [undefined,"","Basic abc","Bearer invalid.jwt","Bearer "+SECRET]) {
    await assert.rejects(oauthVerifier.verify(value),OAuthTokenDenied,"bad bearer");
  }
});

test("metadata only GET; OAuth unauthorized GET blocked",async()=>{
  await withServer(oauthVerifier,async base=>{
    assert.equal((await fetch(base+OAUTH_METADATA_PATH,{method:"POST"})).status,405);
    assert.equal((await fetch(base+"/oauth/mcp")).status,401);
    assert.equal((await fetch(base+"/oauth/mcp",{headers:{Authorization:"Bearer "+await token()}})).status,405);
    assert.equal((await fetch(base+"/mcp",{headers:{Authorization:"Bearer "+SECRET}})).status,405);
  });
});
