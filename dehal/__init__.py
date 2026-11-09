"""DEHAL - DEtecting HALlucinations.

Canonical public name of the verification engine.

Phase A of the rename: the implementation modules still physically live under
'bodulskihal_core'; this package exposes everything under the 'dehal'
name so users can migrate immediately:

    from dehal import Claim, Verdict, verify_claim
    from dehal.dehal_v2 import verify

Phase B (next release) will move the files physically and drop the old name.
New code should import 'dehal' only.
"""
import sys as _sys

from bodulskihal_core import *  # noqa: F401,F403
from bodulskihal_core import (  # noqa: F401
    adapter,
    conversation_gate,
    dehal_v2,
    engine,
    evaluation,
    guard_loop,
    lifecycle,
    raw_pipeline,
    research_demo,
    runtime_provenance,
)
from bodulskihal_core.adapter import (  # noqa: F401
    SCHEMA_VERSION,
    verify_compound_payload,
    verify_payload,
)

# Submodules of dehal_v2, aliased one level deeper for convenience.
from bodulskihal_core.dehal_v2 import (  # noqa: F401
    engine as _v2_engine,
    grounding as _v2_grounding,
    hard as _v2_hard,
    semantic as _v2_semantic,
    snapshot as _v2_snapshot,
)

_ALIASED = (
    "engine",
    "adapter",
    "evaluation",
    "research_demo",
    "guard_loop",
    "lifecycle",
    "raw_pipeline",
    "conversation_gate",
    "runtime_provenance",
    "dehal_v2",
)

for _name in _ALIASED:
    _sys.modules[__name__ + "." + _name] = globals()[_name]

for _name, _module in (
    ("engine", _v2_engine),
    ("grounding", _v2_grounding),
    ("hard", _v2_hard),
    ("semantic", _v2_semantic),
    ("snapshot", _v2_snapshot),
):
    _sys.modules[__name__ + ".dehal_v2." + _name] = _module
