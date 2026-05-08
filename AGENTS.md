# AGENTS.md

## API Philosophy
1. Every public function must have a clean, minimal call signature
2. result = extract(text, schema=Invoice) is the gold standard
3. Never chain abstraction layers: client.router.pipeline.manager.extract() is forbidden
4. No required kwargs beyond text and schema on extract()

## Performance Rules
1. Always attempt orjson fast-path before any repair logic
2. Validation overhead must stay under 10ms — benchmark every PR
3. msgspec is the primary validator — Pydantic only in the optional bridge
4. Never add blocking I/O inside the hot path
5. Async variants must use asyncio natively, never run_in_executor() on sync code

## Code Quality Rules
1. Type hints required on every function signature, no exceptions
2. Docstrings required on all public functions (Google style)
3. ruff check . and mypy . must pass before any commit
4. Unit test required for every new module — 90%+ coverage target
5. No bare except clauses — always catch specific exception types

## Dependency Rules
1. Never introduce a new hard dependency without explicit approval
2. Heavy dependencies (pydantic, openai, anthropic) are optional extras only
3. No dependency on LangChain, LlamaIndex, or any agent framework
4. If you need JSON parsing, use orjson — never stdlib json in hot paths

## DO NOT BUILD
1. Chatbot or agent framework
2. Prompt template management
3. Workflow / DAG orchestrator
4. Vector store or retrieval system
5. GUI, web interface, or dashboard

## Security Rules
1. No eval() or exec() on LLM output under any circumstances
2. Sanitize all malformed inputs before processing
3. Isolate provider integrations cleanly — no cross-contamination
4. Deterministic parsing only — no hidden randomness in core pipeline
