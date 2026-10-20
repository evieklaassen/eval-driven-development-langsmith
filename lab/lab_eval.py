"""Shared eval plumbing for the notebooks and the Checks.

Naming, listing experiments, and averaging feedback are not what anyone is
here to learn, so they live here rather than in every notebook.
"""

import os
from collections import defaultdict

from langsmith import Client


def dataset_name():
    """Dataset name, per project label, so a shared workspace never collides."""
    return f"order-support-{os.environ.get('WORKSHOP_SFX', 'local')}"


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


def failure_modes(prefix="trajectory"):
    """Error analysis: list the newest `prefix` experiment's failing rows and count them by cause."""
    from collections import Counter

    client = Client()
    ds = client.read_dataset(dataset_name=dataset_name())
    exps = experiments(client, ds.id, prefix)
    if not exps:
        print(f"No '{prefix}' experiment yet.")
        return
    exp = exps[-1]
    examples = {e.id: e for e in client.list_examples(dataset_id=ds.id)}
    rows = []
    for run in client.list_runs(project_name=exp.name, is_root=True):
        ex = examples.get(run.reference_example_id)
        if ex is None or not run.outputs:
            continue
        expected, actual = ex.outputs["trajectory"], run.outputs.get("trajectory", [])
        if actual == expected:
            continue
        missing = Counter(expected) - Counter(actual)
        extra = Counter(actual) - Counter(expected)
        if missing:
            cause = "skipped " + ", ".join(sorted(missing))
        elif extra:
            cause = "extra " + ", ".join(sorted(extra))
        else:
            cause = "wrong order"
        rows.append((ex.inputs["query"], expected, actual, cause))
    print(f"{exp.name}: {len(rows)} failing row(s)\n")
    if not rows:
        print("No failing rows: every trajectory matched.")
        return
    for query, expected, actual, cause in rows:
        print(f"query   : {query}")
        print(f"expected: {expected}")
        print(f"actual  : {actual}")
        print(f"cause   : {cause}\n")
    print("Failures by cause (largest first):")
    for cause, n in Counter(r[3] for r in rows).most_common():
        print(f"  {n}  {cause}")
