from dataclasses import dataclass

from agent_registry.registry import AgentRegistry
from agents.agent_messaging import AgentMessaging
from agents.agent_router import AgentRouter
from agents.analysis_agent import AnalysisAgent
from agents.code_agent import CodeAgent
from agents.report_agent import ReportAgent
from agents.research_agent import ResearchAgent
from core.config import Settings
from db.postgres import PostgresClient
from db.redis_client import RedisClient
from llm.gemini_client import GeminiClient
from memory.context_manager import ContextManager
from memory.long_term_memory import LongTermMemory
from memory.short_term_memory import ShortTermMemory
from planner.planner_agent import PlannerAgent
from tools.file_tool import FileTool
from tools.sql_tool import SQLTool
from tools.tool_registry import ToolRegistry
from tools.vector_search_tool import VectorSearchTool
from tools.web_search_tool import WebSearchTool
from workflow.executor import WorkflowExecutor
from workflow.graph_builder import WorkflowGraphBuilder
from workflow.retry_manager import RetryManager
from workflow.workflow_state import WorkflowStateTracker


@dataclass
class AppContainer:
    settings: Settings
    llm_client: GeminiClient
    agent_registry: AgentRegistry
    tool_registry: ToolRegistry
    agent_router: AgentRouter
    messaging: AgentMessaging
    planner_agent: PlannerAgent
    graph_builder: WorkflowGraphBuilder
    state_tracker: WorkflowStateTracker
    executor: WorkflowExecutor
    retry_manager: RetryManager
    context_manager: ContextManager
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
    context_manager = ContextManager(redis_client)
    messaging = AgentMessaging(redis_client)
    tool_registry = ToolRegistry()
    tool_registry.register(WebSearchTool())
    tool_registry.register(FileTool())
    tool_registry.register(SQLTool())
    tool_registry.register(VectorSearchTool())

    agent_registry = AgentRegistry()
    agent_registry.register(ResearchAgent(llm_client, tool_registry, context_manager, messaging))
    agent_registry.register(AnalysisAgent(llm_client, tool_registry, context_manager, messaging))
    agent_registry.register(CodeAgent(llm_client, tool_registry, context_manager, messaging))
    agent_registry.register(ReportAgent(llm_client, tool_registry, context_manager, messaging))

    agent_router = AgentRouter(llm_client)
    planner_agent = PlannerAgent(llm_client, agent_router)
    graph_builder = WorkflowGraphBuilder()
    state_tracker = WorkflowStateTracker()
    retry_manager = RetryManager(settings.workflow_max_retries)
    executor = WorkflowExecutor(
        agent_registry,
        short_term_memory,
        long_term_memory,
        state_tracker,
        context_manager,
        messaging,
        agent_router,
        retry_manager,
    )

    return AppContainer(
        settings=settings,
        llm_client=llm_client,
        agent_registry=agent_registry,
        tool_registry=tool_registry,
        agent_router=agent_router,
        messaging=messaging,
        planner_agent=planner_agent,
        graph_builder=graph_builder,
        state_tracker=state_tracker,
        executor=executor,
        retry_manager=retry_manager,
        context_manager=context_manager,
        short_term_memory=short_term_memory,
        long_term_memory=long_term_memory,
        postgres_client=postgres_client,
        redis_client=redis_client,
    )
