# Evaluation-Driven Development with LangSmith: companion notebooks

The notebooks from the **Evaluation-Driven Development with LangSmith** workshop, runnable on your
own machine. You evaluate one order-support agent: build a dataset, run offline evals, score
single steps and tool-call trajectories, analyze the errors, and fix the agent with the results.

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
git clone <this repo> && cd eval-driven-development-langsmith
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
| 1 | `01_setup_and_baseline` | Connect LangSmith, meet the agent, capture a baseline trace |
| 2 | `02_your_first_offline_eval` | Datasets, target functions, evaluators, `client.evaluate()` |
| 3 | `03_single_step_evals` | Score one decision (`tool_selection`); LLM-as-judge |
| 4 | `04_trajectory_evals` | Score tool-call sequences (`exact_match`, `extra_steps`, `missing_steps`, `in_order`) |
| 5 | `05_the_eval_driven_loop` | Error analysis, change one thing, compare experiments |

The agent (`eval_lab/agent.py`) has four tools over in-memory data and starts with a deliberately
flawed system prompt: it issues refunds without checking eligibility. Whether your model shows the
flaw varies by run, so trust the tables your own evals print.

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
python tools/export_from_track.py /path/to/eval-driven-development-langsmith
```

`README.md`, `pyproject.toml`, `.env.example`, `utils/models.py` and `tools/` are hand-written and
are not overwritten.
