import json
from pathlib import Path
from pprint import pprint

from bodulskihal_core import run_research_demo


fixture_path = Path(__file__).with_name("research_fixture.json")
payload = json.loads(fixture_path.read_text(encoding="utf-8"))
result = run_research_demo(payload)

print(result["human_report"])
print()
print("METRICS")
pprint(result["metrics"])
print()
print("OVERALL", result["overall_verdict"])
