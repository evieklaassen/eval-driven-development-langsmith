"""Collect the learner's LangSmith key in Challenge 1 and store it in .env.

Plumbing, deliberately kept out of the notebook: nobody is here to learn
getpass. The notebook cell is just `from lab_credentials import collect`.
"""

import getpass
import itertools
import os
import re
import unicodedata
from pathlib import Path

ENV = Path(__file__).resolve().parents[1] / ".env"

# LangSmith is regional and a key is only valid in its own region. The region is
# NOT encoded in the key, so the only way to know is to ask each region in turn.
REGIONS = [
    ("US", "https://api.smith.langchain.com"),
    ("EU", "https://eu.api.smith.langchain.com"),
    ("APAC", "https://apac.api.smith.langchain.com"),
    ("AWS US", "https://aws.api.smith.langchain.com"),
]


def _detect_region(api_key):
    """First region where the key really authenticates, as (label, endpoint).

    Uses list_projects rather than Client().info: /info is UNAUTHENTICATED and
    returns 200 for any key at all.
    """
    from langsmith import Client

    for label, url in REGIONS:
        try:
            client = Client(api_key=api_key, api_url=url)
            list(itertools.islice(client.list_projects(), 1))
        except Exception:
            # Never inspect or print the body: a rejected-credential response
            # can echo the submitted key back.
            continue
        return label, url
    return None, None


def probe_tracing(api_key, endpoint, project):
    """None if this workspace accepts new tracing projects, else a short reason.

    A key can authenticate and still be unable to trace: some workspaces require
    an agent to be registered first and answer every trace write with a 403.
    Creating the tracing project is the first write a trace makes, so it fails
    the same way. Returns "agent" or "forbidden"; anything unrecognised is None,
    so an odd response never blocks a learner. Never inspects or prints the body
    beyond matching phrases.
    """
    from langsmith import Client

    try:
        Client(api_key=api_key, api_url=endpoint).create_project(project_name=project)
    except Exception as e:
        text = (type(e).__name__ + " " + str(e)).lower()
        if "conflict" in text or "already exists" in text:
            return None
        if "explicit agent creation" in text or "register the agent" in text:
            return "agent"
        if "403" in text or "forbidden" in text:
            return "forbidden"
    return None


TRACING_BLOCKED = {
    "agent": (
        "Your key works, but this LangSmith workspace blocks tracing until an agent is "
        "registered ('requires explicit agent creation for tracing'). This track sends "
        "traces without registering an agent, so every run would be rejected."
    ),
    "forbidden": (
        "Your key works, but LangSmith refused to create a tracing project (403). "
        "Use a key with permission to create projects and send traces."
    ),
}
TRACING_FIX = (
    "Create a key in a workspace that allows tracing, such as a personal workspace, "
    "then re-run this cell."
)


def _slugify(text):
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "", plain.lower())[:20]


def _store(updates):
    """Rewrite .env in place at 0600, preserving every unrelated line."""
    lines = ENV.read_text().splitlines() if ENV.exists() else []
    kept = [l for l in lines if l.split("=", 1)[0] not in updates]
    body = "\n".join(kept + [f"{k}={v}" for k, v in updates.items()]) + "\n"
    fd = os.open(str(ENV), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(body)
    os.chmod(str(ENV), 0o600)


def _project_name(label):
    base = os.environ.get("WORKSHOP_PROJECT_BASE", "eval-driven-dev")
    return f"{base}-{label}" if label else base


def collect():
    """Prompt for the key, verify it live, and switch tracing on."""
    ls_key = getpass.getpass("LangSmith API key (input hidden): ").strip()
    if not ls_key.startswith("lsv2_"):
        raise SystemExit(
            "That doesn't look like a LangSmith key - they start with 'lsv2_'. "
            "Re-run this cell."
        )
    os.environ["LANGSMITH_API_KEY"] = ls_key

    print("Checking your key against each LangSmith region...")
    region, endpoint = _detect_region(ls_key)
    if endpoint is None:
        raise SystemExit(
            "That key did not authenticate in any LangSmith region "
            "(US, EU, APAC, AWS US). Check it and re-run this cell."
        )

    # Every LangSmith client in this track is a bare Client(), which reads
    # LANGSMITH_ENDPOINT from the environment.
    updates = {
        "LANGSMITH_API_KEY": ls_key,
        "LANGSMITH_TRACING": "true",
        "LANGSMITH_ENDPOINT": endpoint,
    }

    # Not a secret, so unlike the key above this one is echoed as it is typed.
    label = _slugify(input("Short name or initials for your project (e.g. jdoe): "))
    project = _project_name(label)
    updates["LANGSMITH_PROJECT"] = project
    # Names the dataset (internal-assistant-<label>), so every notebook finds the same one.
    updates["WORKSHOP_SFX"] = label or "local"

    blocked = probe_tracing(ls_key, endpoint, project)
    if blocked:
        raise SystemExit(f"{TRACING_BLOCKED[blocked]}\n{TRACING_FIX}")

    _store(updates)
    os.environ["LANGSMITH_TRACING"] = "true"
    os.environ["LANGSMITH_PROJECT"] = project
    os.environ["LANGSMITH_ENDPOINT"] = endpoint
    os.environ["WORKSHOP_SFX"] = label or "local"

    print("✅ Key verified and stored. Tracing is ON.")
    print("   region :", region)
    print("   project:", project)
    if not label:
        print("   (no label given, so your project is named after this session)")
