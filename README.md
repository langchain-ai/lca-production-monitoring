# LCA Production Monitoring

Course materials for LangSmith Production Monitoring. This repository currently contains Python materials only.

See [LangChain Academy](https://academy.langchain.com/) for the associated course.

## Setup

From `python/`, run `uv sync`, copy `example.env` to `.env`, and replace the placeholders with your credentials. Exporting the same variables in your shell also works; existing shell values take precedence over `.env`.

Most module exercises generate synthetic traces locally or upload existing traces. They do not invoke an LLM: generation needs no provider or Gateway key, and uploads require `LANGSMITH_API_KEY` and the correct `LANGSMITH_ENDPOINT`. The live [capstone conversation generator](python/capstone/conversation_agents/ConversationGeneratorSetup.md) uses OpenAI chat and embeddings.

## Optional: LangSmith Gateway for capstone chat

Direct OpenAI chat remains the default. To opt in, ask your workspace administrator to [configure Gateway and the OpenAI provider secret](https://docs.langchain.com/langsmith/llm-gateway-admin-setup), and confirm access to `gpt-5-nano`, `gpt-5-mini`, and `gpt-5`. Then set these values in `python/.env` or export them in your shell:

```dotenv
LANGSMITH_GATEWAY=true
LANGSMITH_API_KEY=your_langsmith_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

Replace both placeholders with real keys. `python/model_config.py` explicitly configures the raw OpenAI SDK; the SDK does not read `LANGSMITH_GATEWAY` itself. The existing SDK supports explicit API keys and base URLs, so no dependency upgrade is needed.

- `true`, `1`, or `yes` (case-insensitive) routes capstone chat to `https://gateway.smith.langchain.com/openai/v1`
- `false`, `0`, `no`, unset, or empty leaves chat on direct OpenAI
- A custom root URL, such as `https://eu.gateway.smith.langchain.com`, gets `/openai/v1` appended; do not include that provider path yourself
- A nonempty `LANGSMITH_GATEWAY_API_KEY` overrides `LANGSMITH_API_KEY` for chat only; an empty override falls back to `LANGSMITH_API_KEY`

Missing, blank, and template keys are rejected for the selected chat route. Restart scripts after changing configuration. Do not put a LangSmith key in `OPENAI_API_KEY` or globally redirect `OPENAI_BASE_URL` to Gateway.

**Embeddings remain direct.** The capstone's knowledge-base search and embedding-generation script still need a real `OPENAI_API_KEY`, even with Gateway chat enabled. SQL and knowledge-base tools keep their existing behavior; Gateway only changes chat transport, not model names or providers.

**LangSmith access is separate.** Trace uploads, capstone feedback, and application tracing use `LANGSMITH_API_KEY`, not the Gateway override. `LANGSMITH_TRACING=false` does not disable Gateway routing or Gateway-side tracing. `LANGSMITH_ENDPOINT` selects the tracing/API region; it does not select the Gateway region. Configure any hosted evaluator's provider credentials in LangSmith itself; local `.env` values do not configure server-side evaluators.

For capstone chat setup diagnostics, run `uv run python env_utils.py` from `python/`. This checks the selected chat credential and enabled tracing, not embedding access or remote provider-secret permissions. Missing chat credentials reported here do not block synthetic-trace generation or upload-only lessons. To run the live capstone from the same directory:

```bash
uv run python capstone/conversation_agents/test_conversation.py
```
