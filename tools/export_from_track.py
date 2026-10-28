"""Regenerate this repo's code and notebooks from the Instruqt track.

The track's `track_scripts/setup-workstation` embeds every helper and generates
every notebook, so it stays the single source of truth. This script lifts those
pieces out, swaps the sandbox-only parts (paths, Bedrock, Check buttons, blank
cells) for standalone equivalents, and writes them here.

    python tools/export_from_track.py /path/to/eval-driven-development-langsmith

Hand-written files (README.md, pyproject.toml, .env.example, utils/models.py,
tools/) are not touched.
"""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
track = Path(sys.argv[1]).resolve()
setup = (track / "track_scripts" / "setup-workstation").read_text()


def heredoc(tag):
    m = re.search(r"<<'%s'\n(.*?)\n%s\n" % (tag, tag), setup, re.S)
    assert m, f"heredoc {tag} not found in setup-workstation"
    return m.group(1)


def swap(text, old, new, label):
    assert text.count(old) == 1, f"{label}: expected exactly one match for {old[:50]!r}, got {text.count(old)}"
    return text.replace(old, new)


def write(rel, text):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text if text.endswith("\n") else text + "\n")
    print("wrote", rel)


ROOT_HACK = '''for _p in ("/root/workshop",):
    if _p not in sys.path:
        sys.path.insert(0, _p)
'''
NEW_HACK = '''_ROOT = str(Path(__file__).resolve().parents[1])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
'''

# --- eval_lab -------------------------------------------------------------
agent = heredoc("AGENTEOF")
agent = swap(agent, "import re\nimport sys\n", "import re\nimport sys\nfrom pathlib import Path\n", "agent imports")
agent = swap(agent, ROOT_HACK, NEW_HACK, "agent path")
write("eval_lab/__init__.py", "")
write("eval_lab/agent.py", agent)

evals = heredoc("EVALSEOF")
evals = swap(evals, "import sys\n\nfor _p", "import sys\nfrom pathlib import Path\n\nfor _p", "evaluators imports")
evals = swap(evals, ROOT_HACK, NEW_HACK, "evaluators path")
write("eval_lab/evaluators.py", evals)
write("utils/__init__.py", "")

# --- lab helpers ------------------------------------------------------------
cred = heredoc("CREDEOF")
cred = swap(cred, "from lab_state import mark_done\n\n", "", "cred mark_done import")
cred = swap(cred, 'ENV = Path("/root/workshop/.env")', 'ENV = Path(__file__).resolve().parents[1] / ".env"', "cred env path")
cred = swap(cred, '    mark_done("/tmp/.credentials-ok")\n', "", "cred mark_done call")
cred = swap(cred, '''    sfx = os.environ.get("WORKSHOP_SFX", "")
    base = os.environ.get("WORKSHOP_PROJECT_BASE", "instruqt-eval-driven-dev")
    if label and sfx:
        return f"{base}-{label}-{sfx}"
    if sfx:
        return f"{base}-{sfx}"
    return os.environ["LANGSMITH_PROJECT"]''', '''    base = os.environ.get("WORKSHOP_PROJECT_BASE", "eval-driven-dev")
    return f"{base}-{label}" if label else base''', "cred project name")
cred = swap(cred, '    updates["LANGSMITH_PROJECT"] = project\n',
            '    updates["LANGSMITH_PROJECT"] = project\n    # Names the dataset (internal-assistant-<label>), so every notebook finds the same one.\n    updates["WORKSHOP_SFX"] = label or "local"\n', "cred sfx")
cred = swap(cred, '    os.environ["LANGSMITH_ENDPOINT"] = endpoint\n',
            '    os.environ["LANGSMITH_ENDPOINT"] = endpoint\n    os.environ["WORKSHOP_SFX"] = label or "local"\n', "cred env sfx")
write("lab/lab_credentials.py", cred)
write("lab/lab_trace.py", heredoc("TRACEEOF").replace("this sandbox's", "this run's").replace("in the sandbox", "in your environment"))
labeval = swap(heredoc("LABEVALEOF"), 'BASELINE_FILE = Path("/opt/workshop/ci/baseline.json")', 'BASELINE_FILE = Path(__file__).resolve().parents[1] / "ci" / "baseline.json"', "baseline path")
write("lab/lab_eval.py", labeval.replace("Per-sandbox dataset name, so a shared workspace never collides.", "Dataset name, per project label, so a shared workspace never collides."))

# --- CI gate script ---------------------------------------------------------
ci = heredoc("CIEOF")
ci = swap(ci, '''sys.path.insert(0, "/opt/workshop")
sys.path.insert(0, "/opt/workshop/instruqt")
''', '''sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "lab"))
''', "ci path")
ci = swap(ci, 'load_dotenv("/opt/workshop/.env", override=True)', 'load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=True)', "ci env")
write("ci/run_evals.py", ci)
os.chmod(ROOT / "ci" / "run_evals.py", 0o755)

# --- notebooks ----------------------------------------------------------------
solutions = eval(re.search(r"SOLUTIONS = (\{.*?\n\})\n", heredoc("FILLEOF"), re.S).group(1))
gen = heredoc("GENEOF")
nbdir = ROOT / "notebooks"
nbdir.mkdir(exist_ok=True)
for old in nbdir.glob("*.ipynb"):  # drop notebooks from earlier track versions
    old.unlink()
subprocess.run([sys.executable, "-I", "-c", gen], check=True, env={**os.environ, "NB_OUT": str(nbdir)}, stdout=subprocess.DEVNULL)

GH_ACTIONS = """```yaml
on: pull_request
jobs:
  eval-gate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: "3.12"}
      - run: pip install langsmith langchain langchain-anthropic python-dotenv
      - run: python ci/run_evals.py --change none   # non-zero exit fails the job
        env:
          LANGSMITH_API_KEY: ${{ secrets.LANGSMITH_API_KEY }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
      - uses: actions/upload-artifact@v4
        if: always()
        with: {name: ci_results, path: ci_results/}   # keep the record for every run
```"""

VERIFY = '''import os
from dotenv import load_dotenv
load_dotenv("../.env", override=True)

from lab_credentials import TRACING_BLOCKED, TRACING_FIX, probe_tracing

blocked = probe_tracing(
    os.environ["LANGSMITH_API_KEY"],
    os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com",
    os.environ["LANGSMITH_PROJECT"],
)
if blocked:
    raise SystemExit(f"{TRACING_BLOCKED[blocked]} {TRACING_FIX}")
print("✓ LangSmith key works and the workspace accepts tracing")
print("✓ project:", os.environ["LANGSMITH_PROJECT"])'''

for f in sorted(nbdir.glob("*.ipynb")):
    nb = json.loads(f.read_text())
    for cell in nb["cells"]:
        src = "".join(cell["source"])
        if cell["cell_type"] == "code":
            src = src.replace('("/root/workshop", "/root/workshop/instruqt")', '("..", "../lab")')
            src = src.replace('load_dotenv("/root/workshop/.env", override=True)', 'load_dotenv("../.env", override=True)')
            src = src.replace("/opt/workshop/ci_results", "../ci_results").replace("/opt/workshop/ci/", "../ci/")
            m = re.fullmatch(r"%%bash\n/opt/workshop/\.venv/bin/python \.\./ci/run_evals\.py --change (\S+)\necho exit code: \$\?", src)
            if m:
                src = ("import subprocess, sys\n\n"
                       f"r = subprocess.run([sys.executable, \"../ci/run_evals.py\", \"--change\", \"{m.group(1)}\"], capture_output=True, text=True)\n"
                       "print(r.stdout + r.stderr)\n"
                       "print(\"exit code:\", r.returncode)")
            src = src.replace("from lab_state import mark_done\n", "").replace('mark_done("/tmp/.baseline-ok")\n', "")
            if "verify_connection.py" in src:
                src = VERIFY
            for tag in cell.get("metadata", {}).get("tags", []):
                if tag in solutions:
                    src = "# Solution. In the workshop this cell was blank and you wrote it.\n" + solutions[tag].rstrip("\n")
        else:
            src = src.replace("The key is stored in this sandbox only.", "The key is stored in `.env` at the repo root, which is git-ignored.")
            src = src.replace("Every line above should show ✓. Click **Check**.", "Every line above should show ✓.")
            src = src.replace("**One cell is blank and yours to write.**", "**One cell was blank in the workshop. Here it is filled in, so every cell runs.**")
            src = src.replace("## Your turn:", "## ")
            src = re.sub(r"Paste (this|the code|it) into the blank cell( below)?", "The next cell holds this code", src)
            src = re.sub(r"\n*(---\n+)?Click \*\*Check\*\*[^\n]*", "", src).rstrip()
            src = src.replace("`/opt/workshop/ci/run_evals.py` is provided.", "`ci/run_evals.py` is provided.")
            src = src.replace("For a regulated business that is the failure that matters", "For a business that has to trust its answers that is the failure that matters")
            src = src.replace("## 7. Wire it into GitLab", "## 7. Wire it into CI")
            src = src.replace("A GitLab CI job is the same command. A sketch of `.gitlab-ci.yml` (not run here):", "A CI job is the same command. A sketch of a GitHub Actions workflow (not run here):")
            src = src.replace("Set `LANGSMITH_API_KEY` as a masked CI/CD variable.", "Set `LANGSMITH_API_KEY` as a repository secret.")
            src = re.sub(r"```yaml\neval-gate:.*?```", GH_ACTIONS, src, flags=re.S)
            src = src.replace("`judge_model` is Claude Haiku on Bedrock.", "`judge_model` is the small, cheap model set by `JUDGE_MODEL`.")
        cell["source"] = src.splitlines(keepends=True)
        cell.setdefault("metadata", {}).pop("tags", None) if cell["cell_type"] == "code" else None
    nb["metadata"]["kernelspec"]["display_name"] = "Python 3"
    f.write_text(json.dumps(nb, indent=1) + "\n")
    print("wrote", f.relative_to(ROOT))
