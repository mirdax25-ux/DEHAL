import json
from pathlib import Path
from pprint import pprint

from b_1_2_core import evaluate_benchmark


root = Path(__file__).parent
fixture = json.loads((root / "research_fixture.json").read_text(encoding="utf-8"))
benchmark = json.loads((root / "research_benchmark.json").read_text(encoding="utf-8"))

result = evaluate_benchmark(fixture, benchmark)

print(result["human_summary"])
print()
print("METRICS")
pprint(result["metrics"])
print()
print("HUMAN ATTENTION IDS")
pprint(result["human_attention_claim_ids"])
