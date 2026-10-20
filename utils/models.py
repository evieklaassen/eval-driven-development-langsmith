"""Model initialization for the companion repo.

`model` runs the agent; `judge_model` is the cheaper model used as an
LLM-as-judge in offline evals. The workshop ran both on AWS Bedrock; here they
are provider-agnostic. Set AGENT_MODEL and JUDGE_MODEL in `.env` as
`provider:model`, for example `openai:gpt-4o` (also install `langchain-openai`).
"""

import os

from dotenv import load_dotenv

load_dotenv(override=False)

from langchain.chat_models import init_chat_model

AGENT_MODEL = os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-4-6")
JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "anthropic:claude-haiku-4-5")

model = init_chat_model(AGENT_MODEL, temperature=0)
judge_model = init_chat_model(JUDGE_MODEL, temperature=0)
