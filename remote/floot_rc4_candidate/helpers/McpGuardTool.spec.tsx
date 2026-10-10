import { handle } from "../endpoints/mcp_POST";

async function rpc(body:any) {
  const response = await handle(new Request("http://local/_api/mcp", {
    method:"POST",
    headers:{"Content-Type":"application/json"},
    body:JSON.stringify(body),
  }));
  return { status:response.status, json:await response.json() };
}

describe("BodulHal Guard Loop MCP tool", () => {
  it("lists guard_claim without removing existing tools", async () => {
    const r = await rpc({jsonrpc:"2.0",id:1,method:"tools/list",params:{}});
    const names = r.json.result.tools.map((tool:any) => tool.name);
    expect(names).toContain("health");
    expect(names).toContain("verify_claims");
    expect(names).toContain("verify_manifest");
    expect(names).toContain("guard_claim");
  });

  it("negotiates an unsupported protocol version to the supported version", async () => {
    const r = await rpc({
      jsonrpc:"2.0",
      id:11,
      method:"initialize",
      params:{
        protocolVersion:"bogus-9999",
        capabilities:{},
        clientInfo:{name:"probe",version:"1"},
      },
    });
    expect(r.status).toBe(200);
    expect(r.json.result.protocolVersion).toBe("2025-06-18");
    expect(r.json.result.protocolVersion).not.toBe("bogus-9999");
  });

  it("calls guard_claim through MCP", async () => {
    const args = {
      claim:{
        id:"health_status",
        kind:"observation",
        assertion:{op:"json_equals",pointer:"/status",expected:"ok"},
        sources:[{type:"supplied",id:"health"}],
        max_age_seconds:300,
      },
      evidence:[{
        id:"health",
        data:{status:"ok"},
        observed_at:new Date().toISOString(),
      }],
      self_check:{
        realism:"impossible",
        known:["bounded claim is present"],
        assumptions:[],
        unknowns:[],
        assumptions_reviewed:true,
        unknowns_reviewed:true,
      },
    };
    const r = await rpc({jsonrpc:"2.0",id:2,method:"tools/call",params:{name:"guard_claim",arguments:args}});
    expect(r.status).toBe(200);
    expect(r.json.result.structuredContent.status).toBe("BLOCK");
    expect(r.json.result.structuredContent.reason).toBe("self_check_impossible");
  });

  it("rejects duplicate raw JSON object keys before dispatch", async () => {
    const raw = '{"jsonrpc":"2.0","id":21,"method":"tools/call","params":{"name":"verify_claims","arguments":{"claims":[{"id":"c1","kind":"observation","assertion":{"op":"json_equals","pointer":"/state","expected":"ok"},"sources":[{"type":"supplied","id":"e1"}],"max_age_seconds":300}],"evidence":[{"id":"e1","data":{"state":"bad","state":"ok"},"observed_at":"2026-09-27T16:29:55Z"}]}}}';
    const response = await handle(new Request("http://local/_api/mcp", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:raw,
    }));
    expect(response.status).toBe(400);
    const json:any = await response.json();
    expect(json.error?.code).toBe(-32700);
  });

  it("rejects unsafe integer literals before numeric precision is lost", async () => {
    const raw = '{"jsonrpc":"2.0","id":22,"method":"tools/call","params":{"name":"verify_claims","arguments":{"claims":[{"id":"c1","kind":"observation","assertion":{"op":"json_equals","pointer":"/n","expected":9007199254740992},"sources":[{"type":"supplied","id":"e1"}],"max_age_seconds":300}],"evidence":[{"id":"e1","data":{"n":9007199254740993},"observed_at":"2026-09-27T16:29:55Z"}]}}}';
    const response = await handle(new Request("http://local/_api/mcp", {
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:raw,
    }));
    expect(response.status).toBe(400);
    const json:any = await response.json();
    expect(json.error?.code).toBe(-32700);
  });
});
