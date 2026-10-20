"""Print links to this run's LangSmith project and to individual traces."""

import os

from langchain_core.tracers.langchain import wait_for_all_tracers
from langsmith import Client


def _ui_host():
    # The UI host mirrors the API host for your region: dropping "api." is the
    # whole mapping. `or` rather than a get() default: the variable is always
    # PRESENT in your environment and is empty for a US-region key.
    api = os.environ.get("LANGSMITH_ENDPOINT") or "https://api.smith.langchain.com"
    return api.replace("api.smith", "smith")


def project_link():
    """Print the tracing project URL."""
    wait_for_all_tracers()
    ui = _ui_host()
    project = os.environ["LANGSMITH_PROJECT"]
    try:
        p = Client().read_project(project_name=project)
        print("Your traces:")
        print(f"  {ui}/o/{p.tenant_id}/projects/p/{p.id}")
    except Exception:
        # Never print the error body: a credential failure can echo the key back.
        print(f"Open {ui} and choose project:", project)


def trace_link(run_id):
    """Print the URL of one trace. Pass the run_id given to invoke() in config."""
    wait_for_all_tracers()
    ui = _ui_host()
    project = os.environ["LANGSMITH_PROJECT"]
    try:
        p = Client().read_project(project_name=project)
        print(f"\nView the trace: {ui}/o/{p.tenant_id}/projects/p/{p.id}/r/{run_id}?poll=true")
    except Exception:
        print(f"\nOpen {ui} and choose project:", project)
