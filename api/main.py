from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.task_routes import router as task_router
from api.routes.workflow_routes import router as workflow_router
from core.config import get_settings
from core.dependencies import AppContainer, build_container
from core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    settings = get_settings()
    container: AppContainer = await build_container(settings)
    app.state.container = container
    yield


app = FastAPI(title="Orion", version="0.1.0", lifespan=lifespan)
app.include_router(task_router)
app.include_router(workflow_router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "orion"}
