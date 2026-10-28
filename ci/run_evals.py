#!/usr/bin/env python
"""Pre-release eval gate: run the evals on a pinned dataset version, compare to a baseline.

Exit 0 if no metric regressed, 1 if one did. In CI, a non-zero exit fails the job.

  run_evals.py --change none             the agent as it is
  run_evals.py --change drop-retrieval   simulate a bad change: the search tool is removed

Every run writes ci_results/<change>.json: what was checked, against what, and the verdict.
"""
import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)
from langsmith import Client

import lab_eval
from eval_lab.agent import SYSTEM_PROMPT_V2, TOOLS, build_agent
from eval_lab.evaluators import groundedness, keyword_match, make_run_agent, tool_selection

ap = argparse.ArgumentParser()
ap.add_argument("--change", choices=["none", "drop-retrieval"], default="none")
ap.add_argument("--tolerance", type=float, default=0.15)
args = ap.parse_args()

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT.parent / "ci_results"

try:
    from gate import find_regressions
except ImportError:
    sys.exit("gate.py not found. Write the gate in the notebook and run the cell that saves it.")
if not (ROOT / "baseline.json").exists():
    sys.exit("baseline.json not found. Record it in the notebook with lab_eval.write_baseline('v2-fixed').")
baseline = json.loads((ROOT / "baseline.json").read_text())

tools = [t for t in TOOLS if t.name != "search_confluence"] if args.change == "drop-retrieval" else TOOLS
agent = build_agent(SYSTEM_PROMPT_V2, tools=tools)

client = Client()
results = client.evaluate(
    make_run_agent(agent),
    data=lab_eval.pinned_examples(client),
    evaluators=[groundedness, tool_selection, keyword_match],
    experiment_prefix=f"ci-{args.change}",
    metadata={"change": args.change, "dataset_version": lab_eval.DATASET_TAG,
              "commit": os.environ.get("CI_COMMIT_SHA", "local")},
    max_concurrency=4,
)

totals, counts = defaultdict(float), defaultdict(int)
for row in results:
    for r in row["evaluation_results"]["results"]:
        if r.score is not None:
            totals[r.key] += r.score
            counts[r.key] += 1
scores = {k: round(totals[k] / counts[k], 3) for k in totals}

regressions = find_regressions(scores, baseline["scores"], args.tolerance)
record = {
    "change": args.change,
    "experiment": results.experiment_name,
    "dataset": lab_eval.dataset_name(),
    "dataset_version": lab_eval.DATASET_TAG,
    "commit": os.environ.get("CI_COMMIT_SHA", "local"),
    "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    "baseline_experiment": baseline["experiment"],
    "baseline": baseline["scores"],
    "scores": scores,
    "tolerance": args.tolerance,
    "regressions": regressions,
    "verdict": "fail" if regressions else "pass",
}
RESULTS.mkdir(exist_ok=True)
out = RESULTS / f"{args.change}.json"
tmp = out.with_suffix(".tmp")
tmp.write_text(json.dumps(record, indent=2) + "\n")
os.chmod(tmp, 0o666)
os.replace(tmp, out)

print(f"experiment : {record['experiment']}")
print(f"{'metric':<14}{'baseline':>10}{'this run':>10}")
for key in lab_eval.GATE_KEYS:
    print(f"{key:<14}{baseline['scores'].get(key, float('nan')):>10.2f}{scores.get(key, float('nan')):>10.2f}")
if regressions:
    print("\nGATE FAILED")
    for msg in regressions:
        print(f"  - {msg}")
    sys.exit(1)
print("\nGATE PASSED")
