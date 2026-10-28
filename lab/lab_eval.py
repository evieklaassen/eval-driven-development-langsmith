"""Shared eval plumbing for the notebooks, the CI script and the Checks.

Naming, listing experiments, and averaging feedback are not what anyone is
here to learn, so they live here rather than in every notebook.
"""

import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

from langsmith import Client

DATASET_TAG = "v1"
BASELINE_FILE = Path(__file__).resolve().parents[1] / "ci" / "baseline.json"
GATE_KEYS = ("groundedness", "tool_selection")


def dataset_name():
    """Dataset name, per project label, so a shared workspace never collides."""
    return f"internal-assistant-{os.environ.get('WORKSHOP_SFX', 'local')}"


def pinned_examples(client):
    """The examples of the dataset version tagged DATASET_TAG, so every run scores the same questions."""
    return list(client.list_examples(dataset_name=dataset_name(), as_of=DATASET_TAG))


def experiments(client, dataset_id, prefix=""):
    """Experiments (projects) on this dataset whose name starts with `prefix`, oldest first."""
    found = [p for p in client.list_projects(reference_dataset_id=dataset_id)
             if p.name.startswith(prefix)]
    return sorted(found, key=lambda p: p.start_time)


def experiment_scores(client, project_name):
    """(number of root runs, {feedback key: average score}) for one experiment."""
    runs = list(client.list_runs(project_name=project_name, is_root=True, select=["id"]))
    totals, counts = defaultdict(float), defaultdict(int)
    if runs:
        for fb in client.list_feedback(run_ids=[r.id for r in runs]):
            if fb.score is not None:
                totals[fb.key] += fb.score
                counts[fb.key] += 1
    return len(runs), {k: totals[k] / counts[k] for k in totals}


def compare(prefixes=("",), keys=None):
    """Print one row per experiment: runs and average score per feedback key."""
    client = Client()
    ds = client.read_dataset(dataset_name=dataset_name())
    rows = []
    for p in experiments(client, ds.id):
        if not any(p.name.startswith(x) for x in prefixes):
            continue
        n, scores = experiment_scores(client, p.name)
        rows.append((p.name, n, scores))
    if not rows:
        print("No matching experiments yet.")
        return
    cols = keys or sorted({k for _, _, s in rows for k in s})
    width = max(len(r[0]) for r in rows)
    print(f"{'experiment':<{width}}  runs  " + "  ".join(f"{c:>14}" for c in cols))
    for name, n, scores in rows:
        cells = "  ".join(f"{scores[c]:>14.2f}" if c in scores else f"{'-':>14}" for c in cols)
        print(f"{name:<{width}}  {n:>4}  {cells}")


def failure_modes(prefix="v1-baseline"):
    """Error analysis: list the newest `prefix` experiment's failing rows and count them by cause."""
    client = Client()
    ds = client.read_dataset(dataset_name=dataset_name())
    exps = experiments(client, ds.id, prefix)
    if not exps:
        print(f"No '{prefix}' experiment yet.")
        return
    exp = exps[-1]
    examples = {e.id: e for e in client.list_examples(dataset_id=ds.id)}
    runs = [r for r in client.list_runs(project_name=exp.name, is_root=True) if r.outputs]
    scores = defaultdict(dict)
    for fb in client.list_feedback(run_ids=[r.id for r in runs]):
        if fb.score is not None:
            scores[fb.run_id][fb.key] = fb.score
    rows = []
    for run in runs:
        ex = examples.get(run.reference_example_id)
        if ex is None:
            continue
        expected, actual = ex.outputs["trajectory"], run.outputs.get("trajectory", [])
        causes = []
        if scores[run.id].get("groundedness") == 0:
            causes.append("ungrounded answer")
        for tool in sorted(set(expected) - set(actual)):
            causes.append(f"skipped {tool}")
        for tool in sorted(set(actual) - set(expected)):
            causes.append(f"extra {tool}")
        if causes:
            rows.append((ex.inputs["query"], expected, actual, causes))
    print(f"{exp.name}: {len(rows)} failing row(s)\n")
    if not rows:
        print("No failing rows: every answer was grounded and every tool choice matched.")
        return
    for query, expected, actual, causes in rows:
        print(f"question: {query}")
        print(f"expected: {expected}")
        print(f"actual  : {actual}")
        print(f"causes  : {', '.join(causes)}\n")
    print("Failures by cause (largest first):")
    for cause, n in Counter(c for r in rows for c in r[3]).most_common():
        print(f"  {n}  {cause}")


def write_baseline(prefix="v2-fixed"):
    """Record the newest `prefix` experiment's scores as the baseline the CI gate compares against."""
    client = Client()
    ds = client.read_dataset(dataset_name=dataset_name())
    exps = experiments(client, ds.id, prefix)
    if not exps:
        raise SystemExit(f"No '{prefix}' experiment yet. Run challenge 4 first.")
    n, scores = experiment_scores(client, exps[-1].name)
    baseline = {
        "experiment": exps[-1].name,
        "dataset_version": DATASET_TAG,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "scores": {k: round(scores[k], 3) for k in GATE_KEYS if k in scores},
    }
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = BASELINE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(baseline, indent=2) + "\n")
    os.chmod(tmp, 0o666)
    os.replace(tmp, BASELINE_FILE)
    print(json.dumps(baseline, indent=2))
