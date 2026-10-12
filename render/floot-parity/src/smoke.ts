/** One-shot authenticated live-loopback parity probe.
 * Uses only the staging credential from the server process environment.
 * No credential, full request, or sensitive evidence is logged.
 */
import { SERVER_VERSION, CORE_DIGEST } from "./BodulHalCore.js";

const expected = ["health", "verify_claims", "verify_manifest", "guard_claim"];

export async function smokeTest(port: number, secret: string): Promise<void> {
  const base = "http://127.0.0.1:" + port + "/mcp";
  let phase = "denied_without_token";
  let rpcId = 0;
  const authHeaders = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
    "authorization": "Bearer " + secret,
  };

  async function rpc(method: string, params: unknown = {}): Promise<any> {
    const response = await fetch(base, {
      method: "POST",
      headers: authHeaders,
      body: JSON.stringify({jsonrpc:"2.0", id:++rpcId, method, params}),
      signal: AbortSignal.timeout(12000),
    });
    if (response.status !== 200) throw new Error("bad_http_status");
    const data = await response.json() as any;
    if (!data.result || data.error) throw new Error("bad_jsonrpc_result");
    return data.result;
  }

  try {
    const denied = await fetch(base, {signal:AbortSignal.timeout(12000)});
    if (denied.status !== 401) throw new Error("unauthorized_not_rejected");
    phase = "initialize";
    const init = await rpc("initialize", {
      protocolVersion:"2025-06-18",
      capabilities:{},
      clientInfo:{name:"BodulHal-staging-parity",version:"1"},
    });
    if (init.serverInfo?.version !== SERVER_VERSION) throw new Error("core_version_mismatch");
    phase = "tools/list";
    const list = await rpc("tools/list");
    const names = list.tools?.map((x:any) => x.name).sort();
    if (JSON.stringify(names) !== JSON.stringify([...expected].sort())) throw new Error("tool_names_mismatch");

    phase = "tools/call health";
    const health = (await rpc("tools/call", {name:"health", arguments:{}})).structuredContent;
    if (health?.version !== SERVER_VERSION || health?.core_sha256 !== CORE_DIGEST)
      throw new Error("health_fingerprint_mismatch");

    const stamp = new Date().toISOString();
    const observation = {
      id:"sample",
      kind:"observation",
      assertion:{op:"json_equals",pointer:"/ready",expected:true},
      sources:[{type:"supplied",id:"fixture"}],
      max_age_seconds:300,
    };
    const evidence = [{id:"fixture",data:{ready:true},observed_at:stamp}];

    phase = "tools/call verify_claims";
    const verified = (await rpc("tools/call", {
      name:"verify_claims",arguments:{claims:[observation],evidence},
    })).structuredContent;
    if (verified?.status !== "APPROVE" || verified?.classification !== "FACT")
      throw new Error("verify_claims_failed");

    phase = "tools/call verify_manifest";
    const manifest = (await rpc("tools/call", {
      name:"verify_manifest",arguments:{manifest:{schema_version:1,claims:[observation]},evidence},
    })).structuredContent;
    if (manifest?.status !== "APPROVE" || manifest?.classification !== "FACT")
      throw new Error("verify_manifest_failed");

    phase = "tools/call guard_claim";
    const guarded = (await rpc("tools/call", {
      name:"guard_claim",
      arguments:{
        claim: observation,
        evidence,
        self_check:{
          realism:"possible",
          known:["Synthetic fixture only"],
          assumptions:[],
          unknowns:[],
          assumptions_reviewed:true,
          unknowns_reviewed:true,
        },
      },
    })).structuredContent;
    if (guarded?.status !== "APPROVE" || guarded?.approved !== true)
      throw new Error("guard_claim_failed");

    phase = "negative_strict_json_types";
    const negative = (await rpc("tools/call", {
      name:"verify_claims",
      arguments:{
        claims:[{...observation,assertion:{op:"json_equals",pointer:"/ready",expected:1}}],
        evidence,
      },
    })).structuredContent;
    if (negative?.approved !== false || negative?.status !== "BLOCK")
      throw new Error("negative_type_check_failed");

    console.log("BODULHAL_RENDER_SELFTEST PASS auth initialize tools/list 4/4 tools negative_type");
  } catch (error) {
    console.log("BODULHAL_RENDER_SELFTEST FAIL phase=" + phase + " type=" +
      (error instanceof Error ? error.name : "Unknown"));
  }
}
