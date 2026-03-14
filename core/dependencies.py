from dataclasses import dataclass

from agent_registry.registry import AgentRegistry
from agents.analysis_agent import AnalysisAgent
from agents.code_agent import CodeAgent
from agents.report_agent import ReportAgent
from agents.research_agent import ResearchAgent
from core.config import Settings
from db.postgres import PostgresClient
from db.redis_client import RedisClient
from llm.gemini_client import GeminiClient
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from planner.planner_agent import PlannerAgent
from workflow.executor import WorkflowExecutor
from workflow.graph_builder import WorkflowGraphBuilder
from workflow.workflow_state import WorkflowStateTracker


@dataclass
class AppContainer:
    settings: Settings
    llm_client: GeminiClient
    agent_registry: AgentRegistry
    planner_agent: PlannerAgent
    graph_builder: WorkflowGraphBuilder
    state_tracker: WorkflowStateTracker
    executor: WorkflowExecutor
    short_term_memory: ShortTermMemory
    long_term_memory: LongTermMemory
    postgres_client: PostgresClient
    redis_client: RedisClient


async def build_container(settings: Settings) -> AppContainer:
    llm_client = GeminiClient(settings)

    postgres_client = PostgresClient(settings.postgres_url)
    await postgres_client.init_models()

    redis_client = RedisClient(settings.redis_url)
    await redis_client.connect()

    short_term_memory = ShortTermMemory(redis_client)
    long_term_memory = LongTermMemory(postgres_client)

    agent_registry = AgentRegistry()
    agent_registry.register(ResearchAgent(llm_client))
    agent_registry.register(AnalysisAgent(llm_client))
    agent_registry.register(CodeAgent(llm_client))
    agent_registry.register(ReportAgent(llm_client))

    planner_agent = PlannerAgent(llm_client)
    graph_builder = WorkflowGraphBuilder()
    state_tracker = WorkflowStateTracker()
    executor = WorkflowExecutor(agent_registry, short_term_memory, long_term_memory, state_tracker)

    return AppContainer(
        settings=settings,
        llm_client=llm_client,
        agent_registry=agent_registry,
        planner_agent=planner_agent,
        graph_builder=graph_builder,
        state_tracker=state_tracker,
        executor=executor,
        short_term_memory=short_term_memory,
        long_term_memory=long_term_memory,
        postgres_client=postgres_client,
        redis_client=redis_client,
    )
