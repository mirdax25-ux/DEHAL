from copy import deepcopy
import pytest

from experiments.grouped_n1n2_c_s1_s2 import runner as r

ProtocolError = r.ProtocolError
TrustedBoundary = r.TrustedBoundary
canonical = r.canonical
digest = r.digest
strict_json_loads = r.strict_json_loads
default_fixture = r.default_fixture
execute = r.execute
final_n2 = r.final_n2
make_checkpoint = r.make_checkpoint
n1_n2_loop = r.n1_n2_loop
render_readonly = r.render_readonly
s1_verify = r.s1_verify
s2_decide = r.s2_decide
worst_status = r.worst_status

KEY = b"prototype-test-key-32-bytes-long!!"
ANCHOR_KEY = b"independent-anchor-key-32-bytes!"
EVIDENCE_KEY = b"independent-evidence-key-32-bytes"
ACTION_KEY = b"independent-action-key-32-bytes!!"


def b():
    return TrustedBoundary(KEY, ANCHOR_KEY, EVIDENCE_KEY, ACTION_KEY)


def fx():
    boundary = b()
    return boundary, default_fixture(boundary)


def test_valid_full_flow_executes_once_then_noop(tmp_path):
    boundary, f = fx()
    assert f["output"]["terminal_status"] == "PASS"
    action = f["output"]["action"]
    ledger = r.FileNonceLedger(tmp_path / "ledger")
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=f["output"], current_state=f["state"], current_policy=f["policy"], action=action, nonce_ledger=ledger) == "EXECUTED"
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=f["output"], current_state=f["state"], current_policy=f["policy"], action=action, nonce_ledger=ledger) == "NOOP"


@pytest.mark.parametrize("path,value", [
    (("payload","goal_id"), "other-goal"),
    (("payload","state_version"), 8),
    (("payload","state_hash"), "x"*64),
    (("payload","contract_hash"), "y"*64),
    (("payload","evidence_root"), "other-root"),
    (("payload","previous_receipt_hash"), "other-prev"),
    (("payload","phase_id"), "other-phase"),
    (("payload","global_anchor","status"), "UNKNOWN"),
    (("payload","global_anchor","independent"), False),
    (("payload","global_anchor","state_version"), 8),
    (("issuer",), "N1"),
    (("kind",), "candidate"),
    (("v",), "9.9.9"),
    (("mac",), "0"*64),
])
def test_transition_tamper_rejected(path, value):
    boundary, f = fx()
    x = deepcopy(f["transition"])
    target = x
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    with pytest.raises(ProtocolError):
        boundary.verify(x, issuer="S-boundary", kind="transition")


@pytest.mark.parametrize("text", [
    '{"a":1,"a":2}',
    '{"x":NaN}',
    '{"x":Infinity}',
    '{"x":-Infinity}',
])
def test_strict_json_rejects_ambiguous_or_nonfinite(text):
    with pytest.raises((ProtocolError, ValueError)):
        strict_json_loads(text)


@pytest.mark.parametrize("statuses,expected", [
    (("PASS","PASS"), "PASS"),
    (("PASS","UNKNOWN"), "UNKNOWN"),
    (("PASS","BLOCK"), "BLOCK"),
    (("PASS","CONFLICT"), "CONFLICT"),
    (("UNKNOWN","BLOCK"), "BLOCK"),
    (("UNKNOWN","CONFLICT"), "CONFLICT"),
    (("BLOCK","CONFLICT"), "CONFLICT"),
])
def test_status_precedence(statuses, expected):
    assert worst_status(*statuses) == expected


@pytest.mark.parametrize("field,value", [
    ("goal_id", "other"),
    ("state_version", 8),
])
def test_initial_candidate_cannot_cross_transition_identity(field, value):
    boundary, f = fx()
    candidate = deepcopy(f["initial"])
    candidate[field] = value
    with pytest.raises(ProtocolError):
        n1_n2_loop(boundary, initial_candidate=candidate, exchanges=f["exchanges"], transition_receipt=f["transition"])


def test_loop_stops_on_no_material_revision():
    boundary, f = fx()
    same = deepcopy(f["initial"])
    ex = [{"n2":{"round_id":0,"decision":"CHALLENGE","issues":["x"]}, "n1_revision":same}]
    out = n1_n2_loop(boundary, initial_candidate=f["initial"], exchanges=ex, transition_receipt=f["transition"])
    assert out["loop_status"] == "UNKNOWN"


def test_loop_unresolved_challenge_is_conflict():
    boundary, f = fx()
    ex = [{"n2":{"round_id":0,"decision":"CHALLENGE","issues":["x"]}}]
    out = n1_n2_loop(boundary, initial_candidate=f["initial"], exchanges=ex, transition_receipt=f["transition"])
    assert out["loop_status"] == "CONFLICT"


def test_loop_unknown_stops_unknown():
    boundary, f = fx()
    ex = [{"n2":{"round_id":0,"decision":"UNKNOWN","issues":["insufficient-evidence"]}}]
    out = n1_n2_loop(boundary, initial_candidate=f["initial"], exchanges=ex, transition_receipt=f["transition"])
    assert out["loop_status"] == "UNKNOWN"


@pytest.mark.parametrize("mutator", [
    lambda x: x["payload"].__setitem__("candidate_hash", "a"*64),
    lambda x: x["payload"].__setitem__("parent_hash", "b"*64),
    lambda x: x["payload"].__setitem__("round_id", 999),
    lambda x: x["payload"].__setitem__("decision", "CHALLENGE"),
    lambda x: x["payload"].__setitem__("issues", ["hidden"]),
    lambda x: x.__setitem__("issuer", "N1"),
    lambda x: x.__setitem__("mac", "0"*64),
])
def test_n2_receipt_tamper_detected(mutator):
    boundary, f = fx()
    x = deepcopy(f["final_n2"])
    mutator(x)
    with pytest.raises(ProtocolError):
        boundary.verify(x, issuer="N2", kind="review")


def test_n1_cannot_forge_n2_receipt_without_boundary_key():
    boundary, f = fx()
    forged = deepcopy(f["final_n2"])
    forged["payload"]["decision"] = "CLEAR"
    forged["mac"] = digest({k: forged[k] for k in ("v","issuer","kind","payload")})
    with pytest.raises(ProtocolError):
        boundary.verify(forged, issuer="N2", kind="review")


@pytest.mark.parametrize("path,value", [
    (("payload","goal_id"), "other"),
    (("payload","contract_hash"), "c"*64),
    (("payload","state_hash"), "d"*64),
    (("payload","state_version"), 99),
    (("payload","candidate_hash"), "e"*64),
    (("payload","loop_root"), "f"*64),
    (("payload","final_n2_receipt_hash"), "1"*64),
    (("payload","global_anchor","independent"), False),
    (("mac",), "2"*64),
])
def test_checkpoint_tamper_causes_s1_block(path, value):
    boundary, f = fx()
    cp = deepcopy(f["checkpoint"])
    target = cp
    for p in path[:-1]:
        target = target[p]
    target[path[-1]] = value
    s1 = s1_verify(boundary, checkpoint=cp, transition_receipt=f["transition"], final_n2_receipt=f["final_n2"],
                   current_state=f["state"], policy=f["policy"])
    assert boundary.verify(s1, issuer="S1", kind="integrity")["status"] == "BLOCK"


@pytest.mark.parametrize("change", [
    {"version":8},
    {"balance":99},
    {"verified_recipients":[]},
])
def test_state_drift_after_checkpoint_blocks_s1(change):
    boundary, f = fx()
    state = deepcopy(f["state"])
    state.update(change)
    s1 = s1_verify(boundary, checkpoint=f["checkpoint"], transition_receipt=f["transition"], final_n2_receipt=f["final_n2"],
                   current_state=state, policy=f["policy"])
    assert boundary.verify(s1, issuer="S1", kind="integrity")["status"] == "BLOCK"


@pytest.mark.parametrize("policy_change", [
    {"max_amount":30},
    {"allowed_actions":["email"]},
    {"contract_id":"transfer-v2"},
])
def test_policy_change_after_checkpoint_blocks_s1(policy_change):
    boundary, f = fx()
    policy = deepcopy(f["policy"])
    policy.update(policy_change)
    s1 = s1_verify(boundary, checkpoint=f["checkpoint"], transition_receipt=f["transition"], final_n2_receipt=f["final_n2"],
                   current_state=f["state"], policy=policy)
    assert boundary.verify(s1, issuer="S1", kind="integrity")["status"] == "BLOCK"


@pytest.mark.parametrize("state_change,policy_change,expected", [
    ({"balance":20}, {}, "BLOCK"),
    ({"verified_recipients":[]}, {}, "BLOCK"),
    ({}, {"max_amount":20}, "BLOCK"),
    ({}, {"allowed_actions":["email"]}, "BLOCK"),
])
def test_s2_contract_checks_are_independent(state_change, policy_change, expected):
    boundary, f = fx()
    state = deepcopy(f["state"])
    state.update(state_change)
    policy = deepcopy(f["policy"])
    policy.update(policy_change)
    anchor = {
        "status":"PASS","independent":True,"scope":["goal"],"state_version":state["version"],
        "goal_id":"pay-alice","contract_hash":digest(policy),
    }
    anchor_receipt = r.issue_global_anchor(ANCHOR_KEY, anchor)
    evidence_root = "e2"
    evidence_receipt = r.issue_evidence_root(
        EVIDENCE_KEY, evidence_root=evidence_root,
        state_version=state["version"], contract_hash=digest(policy)
    )
    transition = boundary.make_transition_envelope(
        goal_id="pay-alice", state=state, policy=policy,
        evidence_root=evidence_root, previous_receipt_hash="p2", global_anchor=anchor,
        global_anchor_receipt=anchor_receipt, evidence_receipt=evidence_receipt
    )
    initial = deepcopy(f["initial"])
    initial["state_version"] = state["version"]
    ex = [{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}]
    loop = n1_n2_loop(boundary, initial_candidate=initial, exchanges=ex, transition_receipt=transition)
    fn2 = final_n2(boundary, loop_result=loop, review={"round_id":99,"decision":"CLEAR","issues":[]}, transition_receipt=transition)
    cp = make_checkpoint(boundary, transition_receipt=transition, loop_result=loop, final_n2_receipt=fn2)
    s1 = s1_verify(boundary, checkpoint=cp, transition_receipt=transition, final_n2_receipt=fn2, current_state=state, policy=policy)
    out = s2_decide(boundary, checkpoint=cp, s1_receipt=s1, current_state=state, policy=policy)
    assert boundary.verify(out, issuer="S2", kind="terminal")["terminal_status"] == expected


@pytest.mark.parametrize("anchor,expected", [
    ({"status":"UNKNOWN","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}, "UNKNOWN"),
    ({"status":"CONFLICT","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}, "CONFLICT"),
    ({"status":"PASS","independent":False,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}, "UNKNOWN"),
    ({"status":"PASS","independent":True,"scope":["other"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}, "UNKNOWN"),
    ({"status":"PASS","independent":True,"scope":["goal"],"state_version":8,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}, "UNKNOWN"),
])
def test_global_goal_never_inferred_from_contract_pass(anchor, expected):
    boundary = b()
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    anchor_receipt = r.issue_global_anchor(ANCHOR_KEY, anchor)
    evidence_root = "e"
    evidence_receipt = r.issue_evidence_root(
        EVIDENCE_KEY, evidence_root=evidence_root,
        state_version=state["version"], contract_hash=digest(policy)
    )
    transition=boundary.make_transition_envelope(
        goal_id="pay-alice",state=state,policy=policy,
        evidence_root=evidence_root,previous_receipt_hash="p",global_anchor=anchor,
        global_anchor_receipt=anchor_receipt,evidence_receipt=evidence_receipt
    )
    initial={"goal_id":"pay-alice","state_version":7,
             "action":{"type":"transfer","recipient":"alice","amount":40,"memo":"x"}}
    loop=n1_n2_loop(
        boundary, initial_candidate=initial,
        exchanges=[{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}],
        transition_receipt=transition
    )
    fn2=final_n2(
        boundary, loop_result=loop,
        review={"round_id":99,"decision":"CLEAR","issues":[]},
        transition_receipt=transition
    )
    cp=make_checkpoint(boundary,transition_receipt=transition,loop_result=loop,final_n2_receipt=fn2)
    s1=s1_verify(boundary,checkpoint=cp,transition_receipt=transition,final_n2_receipt=fn2,current_state=state,policy=policy)
    s2=s2_decide(boundary,checkpoint=cp,s1_receipt=s1,current_state=state,policy=policy)
    payload=boundary.verify(s2,issuer="S2",kind="terminal")
    assert payload["contract_status"] == "PASS"
    assert payload["terminal_status"] == expected


def test_authenticated_global_anchor_cannot_replay_across_goal():
    boundary, f = fx()
    old_payload = f["transition"]["payload"]
    with pytest.raises(ProtocolError, match="anchor_context_mismatch"):
        boundary.make_transition_envelope(
            goal_id="pay-bob",
            state=f["state"],
            policy=f["policy"],
            evidence_root=old_payload["evidence_root"],
            previous_receipt_hash="new-prev",
            global_anchor=old_payload["global_anchor"],
            global_anchor_receipt=old_payload["global_anchor_receipt"],
            evidence_receipt=old_payload["evidence_receipt"],
        )


def test_authenticated_global_anchor_cannot_replay_across_contract():
    boundary, f = fx()
    old_payload = f["transition"]["payload"]
    policy = deepcopy(f["policy"])
    policy["max_amount"] = 60
    evidence_receipt = r.issue_evidence_root(
        EVIDENCE_KEY,
        evidence_root=old_payload["evidence_root"],
        state_version=f["state"]["version"],
        contract_hash=digest(policy),
    )
    with pytest.raises(ProtocolError, match="anchor_context_mismatch"):
        boundary.make_transition_envelope(
            goal_id="pay-alice",
            state=f["state"],
            policy=policy,
            evidence_root=old_payload["evidence_root"],
            previous_receipt_hash="new-prev",
            global_anchor=old_payload["global_anchor"],
            global_anchor_receipt=old_payload["global_anchor_receipt"],
            evidence_receipt=evidence_receipt,
        )


@pytest.mark.parametrize("presentation", [
    {"text":"ok","terminal_status":"PASS"},
    {"text":"ok","action":{"type":"transfer"}},
    {"text":"ok","state_version":8},
    {"text":"ok","terminal_receipt":{}},
    {"text":"ok","action_hash":"x"},
])
def test_readonly_n1_cannot_add_protected_fields(presentation):
    boundary, f = fx()
    with pytest.raises(ProtocolError):
        render_readonly(boundary, terminal_receipt=f["s2"], presentation=presentation)


@pytest.mark.parametrize("text", ["ok", "odobreno", "translated", "format only", ""])
def test_readonly_n1_may_change_only_explanation(text):
    boundary, f = fx()
    out = render_readonly(boundary, terminal_receipt=f["s2"], presentation={"text":text})
    assert out["terminal_status"] == "PASS"
    assert out["action"] == f["output"]["action"]
    assert out["explanation"] == text


@pytest.mark.parametrize("mutate", [
    "terminal_status", "action_amount", "action_recipient", "action_type",
    "action_hash", "state_version", "receipt_mac"
])
def test_executor_rejects_output_tampering(mutate, tmp_path):
    boundary, f = fx()
    out = deepcopy(f["output"])
    action = deepcopy(f["output"]["action"])
    if mutate == "terminal_status":
        out["terminal_status"]="UNKNOWN"
    elif mutate == "action_amount":
        out["action"]["amount"] += 1
    elif mutate == "action_recipient":
        out["action"]["recipient"]="mallory"
    elif mutate == "action_type":
        out["action"]["type"]="email"
    elif mutate == "action_hash":
        out["action_hash"]="0"*64
    elif mutate == "state_version":
        out["state_version"] += 1
    else:
        out["terminal_receipt"]["mac"]="0"*64
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=out, current_state=f["state"], current_policy=f["policy"], action=action, nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


@pytest.mark.parametrize("change", [
    {"version":8}, {"balance":99}, {"verified_recipients":[]}
])
def test_executor_rejects_state_change_after_s2(change, tmp_path):
    boundary, f = fx()
    state=deepcopy(f["state"])
    state.update(change)
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=f["output"], current_state=state, current_policy=f["policy"], action=f["output"]["action"], nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


@pytest.mark.parametrize("change", [
    {"amount":41}, {"recipient":"mallory"}, {"type":"email"}, {"memo":"changed"}
])
def test_executor_rejects_different_action(change, tmp_path):
    boundary, f = fx()
    action=deepcopy(f["output"]["action"])
    action.update(change)
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=f["output"], current_state=f["state"], current_policy=f["policy"], action=action, nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


def test_receipt_mix_and_match_rejected(tmp_path):
    boundary, f = fx()
    out=deepcopy(f["output"])
    out["action"]["amount"]=39
    assert execute(boundary, action_authority_receipt=f["action_authority"], output=out, current_state=f["state"], current_policy=f["policy"], action=out["action"], nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


def test_s1_receipt_cannot_be_reused_for_other_checkpoint():
    boundary, f = fx()
    cp=deepcopy(f["checkpoint"])
    cp["payload"]["candidate"]["action"]["amount"] = 39
    s2=s2_decide(
        boundary, checkpoint=cp, s1_receipt=f["s1"],
        current_state=f["state"], policy=f["policy"]
    )
    assert boundary.verify(s2, issuer="S2", kind="terminal")["terminal_status"] == "BLOCK"


def test_final_n2_challenge_reaches_terminal_conflict():
    boundary, f = fx()
    loop=f["loop"]
    n2=final_n2(
        boundary, loop_result=loop,
        review={"round_id":99,"decision":"CHALLENGE","issues":["made-up"]},
        transition_receipt=f["transition"]
    )
    cp=make_checkpoint(boundary, transition_receipt=f["transition"], loop_result=loop, final_n2_receipt=n2)
    s1=s1_verify(
        boundary,checkpoint=cp,transition_receipt=f["transition"],
        final_n2_receipt=n2,current_state=f["state"],policy=f["policy"]
    )
    s2=s2_decide(
        boundary,checkpoint=cp,s1_receipt=s1,
        current_state=f["state"],policy=f["policy"]
    )
    payload = boundary.verify(s2,issuer="S2",kind="terminal")
    assert payload["final_n2_status"] == "CONFLICT"
    assert payload["terminal_status"] == "CONFLICT"


@pytest.mark.parametrize(
    "loop_exchanges,final_decision,expected_loop,expected_final,expected_terminal",
    [
        ([{"n2":{"round_id":0,"decision":"CHALLENGE","issues":["x"]}}], "CLEAR", "CONFLICT", "PASS", "CONFLICT"),
        ([{"n2":{"round_id":0,"decision":"UNKNOWN","issues":["missing"]}}], "CLEAR", "UNKNOWN", "PASS", "UNKNOWN"),
        ([{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}], "CHALLENGE", "PASS", "CONFLICT", "CONFLICT"),
        ([{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}], "UNKNOWN", "PASS", "UNKNOWN", "UNKNOWN"),
    ],
)
def test_loop_and_final_n2_statuses_reach_s2(
    loop_exchanges, final_decision, expected_loop, expected_final, expected_terminal
):
    boundary, f = fx()
    loop = n1_n2_loop(
        boundary,
        initial_candidate=f["initial"],
        exchanges=loop_exchanges,
        transition_receipt=f["transition"],
    )
    n2 = final_n2(
        boundary,
        loop_result=loop,
        review={"round_id":99,"decision":final_decision,"issues":["regression"] if final_decision != "CLEAR" else []},
        transition_receipt=f["transition"],
    )
    cp = make_checkpoint(
        boundary,
        transition_receipt=f["transition"],
        loop_result=loop,
        final_n2_receipt=n2,
    )
    s1 = s1_verify(
        boundary,
        checkpoint=cp,
        transition_receipt=f["transition"],
        final_n2_receipt=n2,
        current_state=f["state"],
        policy=f["policy"],
    )
    s2 = s2_decide(
        boundary,
        checkpoint=cp,
        s1_receipt=s1,
        current_state=f["state"],
        policy=f["policy"],
    )
    payload = boundary.verify(s2, issuer="S2", kind="terminal")
    assert payload["loop_status"] == expected_loop
    assert payload["final_n2_status"] == expected_final
    assert payload["terminal_status"] == expected_terminal


def test_canonical_is_stable_for_object_key_order():
    assert canonical({"b":2,"a":1}) == canonical({"a":1,"b":2})


def test_bool_and_int_hash_differ():
    assert digest({"x":True}) != digest({"x":1})


def test_caller_cannot_bypass_loop_with_plain_forged_result():
    boundary, f = fx()
    forged = {
        "candidate": deepcopy(f["initial"]),
        "receipts": [],
        "loop_status": "PASS",
        "loop_root": "caller-forged-root",
    }
    with pytest.raises(ProtocolError):
        final_n2(
            boundary,
            loop_result=forged,
            review={"round_id":99,"decision":"CLEAR","issues":[]},
            transition_receipt=f["transition"],
        )


@pytest.mark.parametrize("mutation", [
    "status", "root", "candidate", "receipts", "loop_receipt_mac",
])
def test_loop_result_tamper_cannot_reach_final_n2(mutation):
    boundary, f = fx()
    loop = deepcopy(f["loop"])
    if mutation == "status":
        loop["loop_status"] = "UNKNOWN"
    elif mutation == "root":
        loop["loop_root"] = "tampered-root"
    elif mutation == "candidate":
        loop["candidate"]["action"]["amount"] += 1
    elif mutation == "receipts":
        loop["receipts"] = []
    else:
        loop["loop_receipt"]["mac"] = "0" * 64
    with pytest.raises(ProtocolError):
        final_n2(
            boundary,
            loop_result=loop,
            review={"round_id":99,"decision":"CLEAR","issues":[]},
            transition_receipt=f["transition"],
        )


def _terminal_with_anchor(boundary, anchor, anchor_receipt=None):
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    evidence_root="anchor-regression"
    evidence_receipt=r.issue_evidence_root(
        EVIDENCE_KEY,evidence_root=evidence_root,
        state_version=state["version"],contract_hash=digest(policy)
    )
    tr=boundary.make_transition_envelope(
        goal_id="pay-alice",state=state,policy=policy,
        evidence_root=evidence_root,previous_receipt_hash="anchor-prev",
        global_anchor=anchor,global_anchor_receipt=anchor_receipt,
        evidence_receipt=evidence_receipt
    )
    initial={"goal_id":"pay-alice","state_version":7,
             "action":{"type":"transfer","recipient":"alice","amount":40,"memo":"x"}}
    loop=n1_n2_loop(
        boundary,initial_candidate=initial,
        exchanges=[{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}],
        transition_receipt=tr
    )
    fn2=final_n2(
        boundary,loop_result=loop,
        review={"round_id":99,"decision":"CLEAR","issues":[]},
        transition_receipt=tr
    )
    cp=make_checkpoint(boundary,transition_receipt=tr,loop_result=loop,final_n2_receipt=fn2)
    s1=s1_verify(boundary,checkpoint=cp,transition_receipt=tr,final_n2_receipt=fn2,current_state=state,policy=policy)
    s2=s2_decide(boundary,checkpoint=cp,s1_receipt=s1,current_state=state,policy=policy)
    return boundary.verify(s2,issuer="S2",kind="terminal")


def test_self_asserted_independent_anchor_without_receipt_stays_unknown():
    boundary=b()
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    terminal=_terminal_with_anchor(boundary,anchor,None)
    assert terminal["contract_status"] == "PASS"
    assert terminal["global_goal_status"] == "UNKNOWN"
    assert terminal["terminal_status"] == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["mac","payload"])
def test_tampered_global_anchor_receipt_rejected(mutation):
    boundary=b()
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    receipt=r.issue_global_anchor(ANCHOR_KEY,anchor)
    if mutation == "mac":
        receipt["mac"]="0"*64
    else:
        receipt["payload"]["state_version"]=8
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",
            state={"version":7,"balance":100,"verified_recipients":["alice"]},
            policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]},
            evidence_root="e",previous_receipt_hash="p",global_anchor=anchor,
            global_anchor_receipt=receipt
        )


def test_global_anchor_receipt_from_wrong_trust_root_rejected():
    boundary=b()
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    receipt=r.issue_global_anchor(b"wrong-anchor-root",anchor)
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",
            state={"version":7,"balance":100,"verified_recipients":["alice"]},
            policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]},
            evidence_root="e",previous_receipt_hash="p",global_anchor=anchor,
            global_anchor_receipt=receipt
        )


def test_global_anchor_receipt_payload_mismatch_rejected():
    boundary=b()
    signed={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    supplied={"status":"UNKNOWN","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    receipt=r.issue_global_anchor(ANCHOR_KEY,signed)
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",
            state={"version":7,"balance":100,"verified_recipients":["alice"]},
            policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]},
            evidence_root="e",previous_receipt_hash="p",global_anchor=supplied,
            global_anchor_receipt=receipt
        )


def _terminal_with_evidence(boundary, evidence_root, evidence_receipt=None):
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    anchor_receipt=r.issue_global_anchor(ANCHOR_KEY,anchor)
    tr=boundary.make_transition_envelope(
        goal_id="pay-alice",state=state,policy=policy,
        evidence_root=evidence_root,previous_receipt_hash="evidence-prev",
        global_anchor=anchor,global_anchor_receipt=anchor_receipt,
        evidence_receipt=evidence_receipt
    )
    initial={"goal_id":"pay-alice","state_version":7,
             "action":{"type":"transfer","recipient":"alice","amount":40,"memo":"x"}}
    loop=n1_n2_loop(
        boundary,initial_candidate=initial,
        exchanges=[{"n2":{"round_id":0,"decision":"CLEAR","issues":[]}}],
        transition_receipt=tr
    )
    fn2=final_n2(
        boundary,loop_result=loop,
        review={"round_id":99,"decision":"CLEAR","issues":[]},
        transition_receipt=tr
    )
    cp=make_checkpoint(boundary,transition_receipt=tr,loop_result=loop,final_n2_receipt=fn2)
    s1=s1_verify(boundary,checkpoint=cp,transition_receipt=tr,final_n2_receipt=fn2,current_state=state,policy=policy)
    s2=s2_decide(boundary,checkpoint=cp,s1_receipt=s1,current_state=state,policy=policy)
    return boundary.verify(s1,issuer="S1",kind="integrity"), boundary.verify(s2,issuer="S2",kind="terminal")


def test_self_asserted_evidence_root_without_receipt_stays_unknown():
    boundary=b()
    s1,terminal=_terminal_with_evidence(boundary,"self-asserted-root",None)
    assert s1["status"] == "UNKNOWN"
    assert terminal["contract_status"] == "PASS"
    assert terminal["global_goal_status"] == "PASS"
    assert terminal["terminal_status"] == "UNKNOWN"


@pytest.mark.parametrize("mutation", ["mac","payload"])
def test_tampered_evidence_receipt_rejected(mutation):
    boundary=b()
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    anchor_receipt=r.issue_global_anchor(ANCHOR_KEY,anchor)
    receipt=r.issue_evidence_root(EVIDENCE_KEY,evidence_root="e",state_version=7,contract_hash=digest(policy))
    if mutation == "mac":
        receipt["mac"]="0"*64
    else:
        receipt["payload"]["evidence_root"]="other"
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",state=state,policy=policy,
            evidence_root="e",previous_receipt_hash="p",global_anchor=anchor,
            global_anchor_receipt=anchor_receipt,evidence_receipt=receipt
        )


def test_evidence_receipt_from_wrong_trust_root_rejected():
    boundary=b()
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    anchor_receipt=r.issue_global_anchor(ANCHOR_KEY,anchor)
    receipt=r.issue_evidence_root(b"wrong-evidence-root-key",evidence_root="e",state_version=7,contract_hash=digest(policy))
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",state=state,policy=policy,
            evidence_root="e",previous_receipt_hash="p",global_anchor=anchor,
            global_anchor_receipt=anchor_receipt,evidence_receipt=receipt
        )


def test_evidence_receipt_binding_mismatch_rejected():
    boundary=b()
    state={"version":7,"balance":100,"verified_recipients":["alice"]}
    policy={"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]}
    anchor={"status":"PASS","independent":True,"scope":["goal"],"state_version":7,"goal_id":"pay-alice","contract_hash":digest({"schema_version":1,"contract_id":"transfer-v1","max_amount":80,"allowed_actions":["transfer"]})}
    anchor_receipt=r.issue_global_anchor(ANCHOR_KEY,anchor)
    receipt=r.issue_evidence_root(EVIDENCE_KEY,evidence_root="different-root",state_version=7,contract_hash=digest(policy))
    with pytest.raises(ProtocolError):
        boundary.make_transition_envelope(
            goal_id="pay-alice",state=state,policy=policy,
            evidence_root="e",previous_receipt_hash="p",global_anchor=anchor,
            global_anchor_receipt=anchor_receipt,evidence_receipt=receipt
        )


def test_executor_rejects_policy_drift_after_s2(tmp_path):
    boundary, f = fx()
    changed = deepcopy(f["policy"])
    changed["max_amount"] = 10
    assert r._contract_status(
        {"action": f["output"]["action"]},
        f["state"],
        changed,
    ) == "BLOCK"
    assert execute(boundary, action_authority_receipt=f["action_authority"],
        output=f["output"],
        current_state=f["state"],
        current_policy=changed,
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"


def test_file_nonce_ledger_blocks_replay_after_boundary_restart(tmp_path):
    first_boundary, f = fx()
    ledger_path = tmp_path / "ledger"
    action = f["output"]["action"]
    assert execute(first_boundary, action_authority_receipt=f["action_authority"],
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=action,
        nonce_ledger=r.FileNonceLedger(ledger_path),
    ) == "EXECUTED"

    restarted_boundary = TrustedBoundary(KEY, ANCHOR_KEY, EVIDENCE_KEY, ACTION_KEY)
    assert execute(restarted_boundary, action_authority_receipt=f["action_authority"],
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=action,
        nonce_ledger=r.FileNonceLedger(ledger_path),
    ) == "NOOP"


def test_executor_fails_closed_without_durable_ledger(tmp_path):
    boundary, f = fx()
    assert execute(boundary, action_authority_receipt=f["action_authority"],
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=None,
    ) == "BLOCK"


def test_s2_recertification_cannot_rotate_execution_token(tmp_path):
    boundary, f = fx()
    ledger = r.FileNonceLedger(tmp_path / "ledger")
    action = f["output"]["action"]
    assert execute(boundary, action_authority_receipt=f["action_authority"],
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=action,
        nonce_ledger=ledger,
    ) == "EXECUTED"

    second_s2 = s2_decide(
        boundary,
        checkpoint=f["checkpoint"],
        s1_receipt=f["s1"],
        current_state=f["state"],
        policy=f["policy"],
    )
    first_terminal = boundary.verify(f["s2"], issuer="S2", kind="terminal")
    second_terminal = boundary.verify(second_s2, issuer="S2", kind="terminal")
    assert first_terminal["execution_token"] == second_terminal["execution_token"]
    assert first_terminal["execution_token"] == r._execution_token("pay-alice")

    second_output = render_readonly(
        boundary,
        terminal_receipt=second_s2,
        presentation={"text": "same goal recertified"},
    )
    assert execute(boundary, action_authority_receipt=f["action_authority"],
        output=second_output,
        current_state=f["state"],
        current_policy=f["policy"],
        action=second_output["action"],
        nonce_ledger=ledger,
    ) == "NOOP"



def test_terminal_pass_is_explicitly_bounded_not_global_truth():
    boundary, f = fx()
    terminal = boundary.verify(f["s2"], issuer="S2", kind="terminal")
    assert terminal["terminal_status"] == "PASS"
    assert terminal["epistemic_scope"] == "authenticated_inputs_and_declared_requirements_only"
    assert terminal["global_truth_certified"] is False
    assert f["output"]["epistemic_scope"] == terminal["epistemic_scope"]
    assert f["output"]["global_truth_certified"] is False


def test_readonly_layer_cannot_upgrade_bounded_pass_to_global_truth(tmp_path):
    boundary, f = fx()
    with pytest.raises(ProtocolError):
        render_readonly(
            boundary,
            terminal_receipt=f["s2"],
            presentation={"text": "Universally correct.", "global_truth_certified": True},
        )
    tampered = deepcopy(f["output"])
    tampered["global_truth_certified"] = True
    assert execute(boundary, action_authority_receipt=f["action_authority"],
        output=tampered,
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"


def test_common_mode_wrong_spec_remains_explicit_trust_boundary():
    boundary, f = fx()
    # Deliberately model a real semantic rule that is absent from every trusted
    # input. The system can only prove conformance to what it was actually given.
    external_requirement = {"max_amount": 30}
    assert f["output"]["action"]["amount"] == 40
    assert f["output"]["action"]["amount"] > external_requirement["max_amount"]
    assert f["output"]["terminal_status"] == "PASS"
    assert f["output"]["global_truth_certified"] is False
    assert f["output"]["epistemic_scope"] == "authenticated_inputs_and_declared_requirements_only"


def test_bounded_pass_without_separate_action_authority_is_blocked(tmp_path):
    boundary, f = fx()
    assert f["output"]["terminal_status"] == "PASS"
    assert f["output"]["global_truth_certified"] is False
    assert f["output"]["epistemic_scope"] == "authenticated_inputs_and_declared_requirements_only"
    # Safety target for this RED attack: a non-globally-certified decision must
    # not itself be sufficient authority for an irreversible side effect.
    result = execute(boundary,
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    )
    assert result == "BLOCK"


def _issue_authority_for_fixture(f, *, secret=ACTION_KEY, **overrides):
    boundary = b()
    terminal = boundary.verify(f["s2"], issuer="S2", kind="terminal")
    payload = {
        "goal_id": terminal["goal_id"],
        "action_hash": terminal["action_hash"],
        "state_hash": terminal["state_hash"],
        "state_version": terminal["state_version"],
        "contract_hash": terminal["contract_hash"],
        "execution_token": terminal["execution_token"],
    }
    payload.update(overrides)
    basis = r.issue_action_basis(
        secret,
        basis_root=digest({"source": "external-test-approval", "approval_id": "helper-approval"}),
        **payload,
    )
    return boundary.issue_action_authority(action_basis_receipt=basis)


@pytest.mark.parametrize("field,value", [
    ("goal_id", "other-goal"),
    ("action_hash", "0"*64),
    ("state_hash", "1"*64),
    ("state_version", 8),
    ("contract_hash", "2"*64),
    ("execution_token", "3"*64),
])
def test_action_authority_is_bound_to_exact_execution_context(field, value, tmp_path):
    boundary, f = fx()
    authority = _issue_authority_for_fixture(f, **{field: value})
    assert execute(
        boundary,
        action_authority_receipt=authority,
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"


def test_action_authority_from_wrong_trust_root_is_blocked(tmp_path):
    boundary, f = fx()
    with pytest.raises(ProtocolError):
        _issue_authority_for_fixture(f, secret=KEY)


def test_action_authority_tamper_is_blocked(tmp_path):
    boundary, f = fx()
    authority = deepcopy(f["action_authority"])
    authority["mac"] = "0"*64
    assert execute(
        boundary,
        action_authority_receipt=authority,
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"


def test_trust_roots_must_be_distinct():
    with pytest.raises(ProtocolError, match="trust_roots_not_distinct"):
        TrustedBoundary(KEY, ANCHOR_KEY, EVIDENCE_KEY, KEY)



def test_action_authority_derived_only_from_s2_cannot_upgrade_bounded_pass_to_execution(tmp_path):
    boundary, f = fx()
    terminal = boundary.verify(f["s2"], issuer="S2", kind="terminal")
    assert terminal["terminal_status"] == "PASS"
    assert terminal["global_truth_certified"] is False

    # Attack: an internally signed capability copied only from S2 context has
    # no separately authenticated external action basis and must fail closed.
    forged = boundary.issue(
        issuer="ACTION-AUTHORITY",
        kind="capability",
        payload={
            "goal_id": terminal["goal_id"],
            "action_hash": terminal["action_hash"],
            "state_hash": terminal["state_hash"],
            "state_version": terminal["state_version"],
            "contract_hash": terminal["contract_hash"],
            "execution_token": terminal["execution_token"],
        },
    )
    result = execute(
        boundary,
        action_authority_receipt=forged,
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    )
    assert result == "BLOCK"
