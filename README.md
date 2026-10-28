# Evaluation-Driven Development with LangSmith: companion notebooks

The notebooks from the **Evaluation-Driven Development with LangSmith** workshop, runnable on your
own machine. You evaluate one internal assistant that answers questions from a knowledge base and
works with tickets: build a versioned dataset, run offline evals, score groundedness and tool use,
analyze the failures, fix the agent, and turn the comparison into a pre-release gate you can run in CI.

All data is synthetic.

Everything you create (dataset, experiments, traces) lives in your own LangSmith workspace.

## Prerequisites

- Python 3.11+ and [uv](https://docs.astral.sh/uv/) (or pip).
- A **LangSmith API key** (`lsv2_...`) from [smith.langchain.com](https://smith.langchain.com) under **Settings** → **API Keys**, with permission to create projects and datasets.
- A workspace that **accepts tracing without registering an agent**. A personal workspace does. Some organization workspaces require explicit agent creation and reject every trace with a 403. Test it first with the check below.
- An **Anthropic API key** for the agent and the LLM judge. To use another provider, see [Using other models](#using-other-models).

Workspace check (set `LANGSMITH_API_KEY` first; for an EU key add `api_url="https://eu.api.smith.langchain.com"`):

```python
import os
from langsmith import Client

c = Client(api_key=os.environ["LANGSMITH_API_KEY"])
c.create_project(project_name="workshop-precheck")
c.delete_project(project_name="workshop-precheck")
print("OK: this workspace accepts tracing projects")
```

A 403 mentioning "explicit agent creation" means this workspace won't work. Use a different one.

## Setup

```bash
git clone <this repo> && cd eval-driven-development-langsmith-companion
cp .env.example .env          # add ANTHROPIC_API_KEY
uv sync
uv run jupyter lab notebooks/
```

Open the notebooks from the `notebooks/` folder and run them in order. Notebook 1 asks for your
LangSmith key and a short project label, checks that your workspace accepts traces, and stores
both in `.env`.

## Notebooks

| # | Notebook | What it covers |
|---|----------|----------------|
| 1 | `01_setup_and_baseline` | Connect LangSmith, meet the assistant, capture a baseline trace |
| 2 | `02_versioned_dataset_first_eval` | Build and tag a dataset version, target functions, `client.evaluate()` |
| 3 | `03_groundedness_and_tool_evals` | LLM-as-judge groundedness, tool selection, error analysis |
| 4 | `04_fix_and_compare` | Change one thing, rerun on the same dataset version, compare experiments |
| 5 | `05_ci_gate` | A regression gate: baseline, tolerance, exit code, results file |

The agent (`eval_lab/agent.py`) has three tools over in-memory data and starts with a deliberately
flawed system prompt: a partly out-of-date "quick reference" that tells it to answer without
searching the knowledge base. Whether your model shows the flaw varies by run, so trust the tables
your own evals print.

Notebook 5 runs `ci/run_evals.py`, which writes `ci/baseline.json` and `ci_results/*.json`.
Both are generated when you run it.

## Differences from the workshop

- Models come from `utils/models.py` (Anthropic by default), not AWS Bedrock.
- Cells that were blank exercises in the workshop are filled in, so every cell runs.
- There are no Check buttons.

## Using other models

Set `AGENT_MODEL` and `JUDGE_MODEL` in `.env` as `provider:model`, for example
`openai:gpt-4o`, and install that provider's package (`uv add langchain-openai`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `403 ... requires explicit agent creation for tracing` | The workspace blocks tracing until an agent is registered | Use a key from a workspace without that policy |
| `ModuleNotFoundError: eval_lab` | Notebook opened with a different working directory | Launch Jupyter and open the notebook from `notebooks/` |
| Authentication error on the first model call | Missing or wrong `ANTHROPIC_API_KEY` | Set it in `.env` and restart the kernel |
| Experiments missing right after a run | LangSmith is eventually consistent | Wait a few seconds and rerun the cell |

## Keeping this repo in sync

The code and notebooks are generated from the workshop's Instruqt track:

```bash
python tools/export_from_track.py /path/to/track
```

`README.md`, `pyproject.toml`, `.env.example`, `utils/models.py` and `tools/` are hand-written and
are not overwritten. Notebooks from earlier versions of the track are removed.
