# Orion

Orion is a multi-agent AI orchestration backend built with FastAPI and async Python. It accepts a user task, plans a workflow of specialized agents, executes the workflow as a dependency graph, and exposes status/results through API endpoints.

## What it does
- Orchestrates four agent roles: research, analysis, code, and report generation.
- Uses an LLM-driven planner to turn one user task into a multi-step execution plan.
- Builds and runs workflow graphs with dependency awareness, retry handling, and bounded concurrency.
- Supports queue-based execution through RabbitMQ, with an in-process fallback when messaging infra is unavailable.
- Persists workflow state/history and agent outputs across in-memory, Redis, and PostgreSQL layers.
- Produces workflow diagrams for execution visibility.

## Core design (high level)
- **API Layer**: Receives task requests and status queries.
- **Planning Layer**: Converts a natural-language task into normalized execution steps.
- **Execution Layer**: Runs graph nodes with retries, timeout polling, and concurrency limits.
- **Agent Layer**: Domain-specialized agents use tools, shared context, and inter-agent messaging.
- **Memory & Persistence Layer**: Redis for short-term/context state; PostgreSQL for long-term workflow history.
- **Messaging Layer**: RabbitMQ queues for asynchronous worker dispatch.

## System characteristics
- Async-first architecture (`FastAPI`, `asyncio`, async DB and queue clients).
- Deterministic fallback behavior when Redis/Postgres/RabbitMQ are unavailable.
- Extensible registries for adding new agents and tools.
- Clear separation of concerns across API, planner, runtime, workers, memory, messaging, and tools.

## Project scope
Orion is currently a backend orchestration platform with placeholder tool implementations for web search, SQL, and vector search, plus a real local file reader tool. The architecture is ready for replacing placeholders with production connectors.
