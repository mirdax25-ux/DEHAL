"""Deterministic property/fuzz regressions for the grouped architecture prototype."""
from __future__ import annotations

from copy import deepcopy
import random
import string

import pytest

from experiments.grouped_n1n2_c_s1_s2 import runner as r


KEY = b"prototype-test-key-32-bytes-long!!"
ANCHOR_KEY = b"independent-anchor-key-32-bytes!"
EVIDENCE_KEY = b"independent-evidence-key-32-bytes"
ACTION_KEY = b"independent-action-key-32-bytes!!"
SEEDS = tuple(range(40))


def boundary():
    return r.TrustedBoundary(KEY, ANCHOR_KEY, EVIDENCE_KEY, ACTION_KEY)


def _action_policy_for(f):
    return {
        "schema_version": 1,
        "policy_id": "independent-action-policy-v1",
        "authority_scope": "external_side_effect",
        "state_version": f["state"]["version"],
        "allowed_goals": ["pay-alice"],
        "max_amount": 80,
        "allowed_actions": ["transfer"],
        "allowed_recipients": ["alice"],
    }


def fixture():
    b = boundary()
    f = r.default_fixture(b)
    action_policy = _action_policy_for(f)
    terminal = b.verify(f["s2"], issuer="S2", kind="terminal")
    f["action_policy"] = action_policy
    f["action_authority"] = r.issue_action_authority(
        b.action_secret,
        action_policy=action_policy,
        goal_id=terminal["goal_id"],
        action=f["output"]["action"],
        state_hash=terminal["state_hash"],
        state_version=terminal["state_version"],
        contract_hash=terminal["contract_hash"],
        execution_token=terminal["execution_token"],
    )
    return b, f


def rand_text(rng, n=10):
    alphabet = string.ascii_letters + string.digits + "_-.:"
    return "".join(rng.choice(alphabet) for _ in range(n))


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_executor_rejects_random_action_mutation(seed, tmp_path):
    rng = random.Random(seed)
    b, f = fixture()
    action = deepcopy(f["output"]["action"])
    choice = rng.choice(("amount", "recipient", "type", "memo"))
    if choice == "amount":
        action["amount"] += rng.randint(1, 100)
    elif choice == "recipient":
        action["recipient"] = "u_" + rand_text(rng, 8)
    elif choice == "type":
        action["type"] = "a_" + rand_text(rng, 8)
    else:
        action["memo"] = "m_" + rand_text(rng, 12)
    assert r.execute(b, action_authority_receipt=f["action_authority"], current_action_policy=f["action_policy"], output=f["output"], current_state=f["state"], current_policy=f["policy"], action=action, nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_executor_rejects_random_state_mutation(seed, tmp_path):
    rng = random.Random(seed)
    b, f = fixture()
    state = deepcopy(f["state"])
    choice = rng.choice(("version", "balance", "verified_recipients"))
    if choice == "version":
        state["version"] += rng.randint(1, 20)
    elif choice == "balance":
        state["balance"] += rng.randint(1, 100)
    else:
        state["verified_recipients"] = ["alice", "u_" + rand_text(rng, 8)]
    assert r.execute(b, action_authority_receipt=f["action_authority"], current_action_policy=f["action_policy"], output=f["output"], current_state=state, current_policy=f["policy"], action=f["output"]["action"], nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_terminal_receipt_tamper_never_executes(seed, tmp_path):
    rng = random.Random(seed)
    b, f = fixture()
    out = deepcopy(f["output"])
    receipt = out["terminal_receipt"]
    choice = rng.choice((
        "mac", "issuer", "kind", "terminal_status", "state_version",
        "state_hash", "action_hash", "execution_token", "contract_hash",
    ))
    if choice in ("mac", "state_hash", "action_hash", "contract_hash"):
        if choice == "mac":
            receipt["mac"] = rand_text(rng, 64)
        else:
            receipt["payload"][choice] = rand_text(rng, 64)
    elif choice == "issuer":
        receipt["issuer"] = "N1"
    elif choice == "kind":
        receipt["kind"] = "review"
    elif choice == "terminal_status":
        receipt["payload"]["terminal_status"] = rng.choice(("UNKNOWN", "BLOCK", "CONFLICT"))
    elif choice == "state_version":
        receipt["payload"]["state_version"] += rng.randint(1, 20)
    elif choice == "execution_token":
        receipt["payload"]["execution_token"] = "nonce_" + rand_text(rng, 10)
    assert r.execute(b, action_authority_receipt=f["action_authority"], current_action_policy=f["action_policy"], output=out, current_state=f["state"], current_policy=f["policy"], action=f["output"]["action"], nonce_ledger=r.FileNonceLedger(tmp_path / "ledger")) == "BLOCK"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_checkpoint_tamper_never_passes_s1(seed):
    rng = random.Random(seed)
    b, f = fixture()
    cp = deepcopy(f["checkpoint"])
    payload = cp["payload"]
    choice = rng.choice((
        "goal_id", "contract_hash", "state_hash", "state_version",
        "evidence_root", "candidate_hash", "loop_root", "final_n2_receipt_hash",
    ))
    if choice == "state_version":
        payload[choice] += rng.randint(1, 20)
    elif choice == "goal_id":
        payload[choice] = "g_" + rand_text(rng, 8)
    else:
        payload[choice] = rand_text(rng, 64)
    s1 = r.s1_verify(
        b,
        checkpoint=cp,
        transition_receipt=f["transition"],
        final_n2_receipt=f["final_n2"],
        current_state=f["state"],
        policy=f["policy"],
    )
    assert b.verify(s1, issuer="S1", kind="integrity")["status"] == "BLOCK"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_readonly_n1_cannot_change_protected_output(seed):
    rng = random.Random(seed)
    b, f = fixture()
    text = rand_text(rng, rng.randint(0, 60))
    out = r.render_readonly(b, terminal_receipt=f["s2"], presentation={"text": text})
    terminal = b.verify(f["s2"], issuer="S2", kind="terminal")
    assert out["terminal_status"] == terminal["terminal_status"]
    assert out["action"] == terminal["action"]
    assert out["action_hash"] == terminal["action_hash"]
    assert out["state_version"] == terminal["state_version"]


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_untrusted_global_anchor_cannot_create_global_pass(seed):
    rng = random.Random(seed)
    b = boundary()
    state = {"version": 7, "balance": 100, "verified_recipients": ["alice"]}
    policy = {"schema_version": 1, "contract_id": "transfer-v1", "max_amount": 80, "allowed_actions": ["transfer"]}

    mode = rng.choice(("not_independent", "wrong_scope", "wrong_version", "unknown"))
    anchor = {
        "status": "PASS", "independent": True, "scope": ["goal"], "state_version": 7,
        "goal_id": "pay-alice", "contract_hash": r.digest(policy),
    }
    if mode == "not_independent":
        anchor["independent"] = False
    elif mode == "wrong_scope":
        anchor["scope"] = ["other"]
    elif mode == "wrong_version":
        anchor["state_version"] = 8 + rng.randint(0, 20)
    else:
        anchor["status"] = "UNKNOWN"

    evidence_root = "evidence-root"
    evidence_receipt = r.issue_evidence_root(
        EVIDENCE_KEY, evidence_root=evidence_root,
        state_version=state["version"], contract_hash=r.digest(policy)
    )
    tr = b.make_transition_envelope(
        goal_id="pay-alice",
        state=state,
        policy=policy,
        evidence_root=evidence_root,
        previous_receipt_hash="previous-root",
        global_anchor=anchor,
        evidence_receipt=evidence_receipt,
    )
    initial = {
        "goal_id": "pay-alice",
        "state_version": 7,
        "action": {"type": "transfer", "recipient": "alice", "amount": 40, "memo": "x"},
    }
    loop = r.n1_n2_loop(
        b,
        initial_candidate=initial,
        exchanges=[{"n2": {"round_id": 0, "decision": "CLEAR", "issues": []}}],
        transition_receipt=tr,
    )
    fn2 = r.final_n2(
        b,
        loop_result=loop,
        review={"round_id": 99, "decision": "CLEAR", "issues": []},
        transition_receipt=tr,
    )
    cp = r.make_checkpoint(b, transition_receipt=tr, loop_result=loop, final_n2_receipt=fn2)
    s1 = r.s1_verify(
        b, checkpoint=cp, transition_receipt=tr, final_n2_receipt=fn2,
        current_state=state, policy=policy
    )
    s2 = r.s2_decide(
        b, checkpoint=cp, s1_receipt=s1, current_state=state, policy=policy,
    )
    terminal = b.verify(s2, issuer="S2", kind="terminal")
    assert terminal["contract_status"] == "PASS"
    assert terminal["terminal_status"] == "UNKNOWN"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_status_precedence_never_allows_pass_to_override_stronger_state(seed):
    rng = random.Random(seed)
    statuses = [rng.choice(("PASS", "UNKNOWN", "BLOCK", "CONFLICT")) for _ in range(rng.randint(1, 8))]
    expected = max(statuses, key=lambda s: r.STATUS_ORDER[s])
    assert r.worst_status(*statuses) == expected
    if any(s != "PASS" for s in statuses):
        assert r.worst_status(*statuses) != "PASS"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_loop_is_bounded_and_repeated_candidate_does_not_unlock_pass(seed):
    rng = random.Random(seed)
    b, f = fixture()
    initial = deepcopy(f["initial"])
    exchanges = []
    for i in range(rng.randint(1, 12)):
        exchanges.append({
            "n2": {"round_id": i, "decision": "CHALLENGE", "issues": ["issue"]},
            "n1_revision": deepcopy(initial),
        })
    out = r.n1_n2_loop(
        b,
        initial_candidate=initial,
        exchanges=exchanges,
        transition_receipt=f["transition"],
        max_rounds=rng.randint(1, 4),
    )
    assert out["loop_status"] == "UNKNOWN"
    assert len(out["receipts"]) <= 1


def test_property_canonical_object_order_invariant_for_many_objects():
    rng = random.Random(20261004)
    for _ in range(500):
        items = [(f"k{i}", rng.randint(-100000, 100000)) for i in range(rng.randint(1, 20))]
        a = dict(items)
        rng.shuffle(items)
        b = dict(items)
        assert r.canonical(a) == r.canonical(b)
        assert r.digest(a) == r.digest(b)


def test_property_bool_never_aliases_integer_hash():
    for key in ("x", "value", "status", "flag"):
        assert r.digest({key: True}) != r.digest({key: 1})
        assert r.digest({key: False}) != r.digest({key: 0})


def _consume_nonce_worker(ledger_path, nonce, queue):
    try:
        queue.put(r.FileNonceLedger(ledger_path).consume(nonce))
    except Exception as exc:
        queue.put(("ERR", type(exc).__name__))


def test_multiprocess_nonce_ledger_allows_exactly_one_consumer(tmp_path):
    import multiprocessing as mp
    ctx = mp.get_context("spawn")
    queue = ctx.Queue()
    ledger_path = str(tmp_path / "ledger-mp")
    nonce = "nonce_parallel_20261004"
    workers = [ctx.Process(target=_consume_nonce_worker, args=(ledger_path, nonce, queue)) for _ in range(16)]
    for proc in workers:
        proc.start()
    for proc in workers:
        proc.join(15)
        assert proc.exitcode == 0
    results = [queue.get(timeout=5) for _ in workers]
    assert results.count(True) == 1
    assert results.count(False) == len(workers) - 1
    assert not any(isinstance(item, tuple) and item[0] == "ERR" for item in results)

@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_action_authority_tamper_never_executes(seed, tmp_path):
    rng = random.Random(seed)
    b, f = fixture()
    authority = deepcopy(f["action_authority"])
    choice = rng.choice(("mac", "issuer", "kind", "goal_id", "action_hash", "state_hash", "state_version", "contract_hash", "execution_token", "action_policy_id", "action_policy_hash", "authority_scope"))
    if choice == "mac":
        authority["mac"] = rand_text(rng, 64)
    elif choice == "issuer":
        authority["issuer"] = "N1"
    elif choice == "kind":
        authority["kind"] = "review"
    elif choice == "state_version":
        authority["payload"][choice] += rng.randint(1, 20)
    elif choice == "goal_id":
        authority["payload"][choice] = "g_" + rand_text(rng, 8)
    else:
        authority["payload"][choice] = ("0" if authority["payload"][choice][0] != "0" else "1") + authority["payload"][choice][1:]
    assert r.execute(
        b,
        action_authority_receipt=authority,
        current_action_policy=f["action_policy"],
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"


@pytest.mark.parametrize("seed", SEEDS)
def test_fuzz_action_policy_mutation_never_executes(seed, tmp_path):
    rng = random.Random(seed)
    b, f = fixture()
    policy = deepcopy(f["action_policy"])
    choice = rng.choice((
        "max_amount", "state_version", "allowed_goals", "allowed_actions",
        "allowed_recipients", "policy_id", "authority_scope",
    ))
    if choice == "max_amount":
        policy[choice] = rng.randint(1, 39)
    elif choice == "state_version":
        policy[choice] += rng.randint(1, 20)
    elif choice == "allowed_goals":
        policy[choice] = ["other-goal"]
    elif choice == "allowed_actions":
        policy[choice] = ["other-action"]
    elif choice == "allowed_recipients":
        policy[choice] = ["bob"]
    elif choice == "policy_id":
        policy[choice] = "other-action-policy"
    else:
        policy[choice] = "other_scope"
    assert r.execute(
        b,
        action_authority_receipt=f["action_authority"],
        current_action_policy=policy,
        output=f["output"],
        current_state=f["state"],
        current_policy=f["policy"],
        action=f["output"]["action"],
        nonce_ledger=r.FileNonceLedger(tmp_path / "ledger"),
    ) == "BLOCK"
