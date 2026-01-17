"""
Web UI for Gmail Secretary - AI-powered email client.

Provides a human interface to the email system with:
- Inbox view with pagination
- Thread/conversation view
- Semantic search
- AI assistant integration (configurable LLM)
- Authentication (password, OIDC, SAML2)
"""

import logging
import asyncio
import os
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from pathlib import Path

from workspace_secretary.config import WebConfig, load_config_with_oauth2

logger = logging.getLogger(__name__)

_executor_task: Optional[asyncio.Task] = None

# Initialize Jinja2 templates
_templates_dir = Path(__file__).parent / "templates"
templates = Jinja2Templates(directory=str(_templates_dir))


def _running_in_docker() -> bool:
    if os.environ.get("DOCKER_ENV"):
        return True
    return Path("/.dockerenv").exists()


def _strftime_filter(value, format_string: str) -> str:
    """Format datetime value using strftime. Handles ISO strings and datetime objects."""
    if value is None:
        return ""
    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return value
    if isinstance(value, datetime):
        return value.strftime(format_string)
    return str(value)


templates.env.filters["strftime"] = _strftime_filter

_web_config: Optional[WebConfig] = None

HEALTH_CHECK_INTERVAL_SECONDS = 300
HEALTH_CHECK_INITIAL_DELAY_SECONDS = 60


async def _health_check_loop():
    from workspace_secretary.web.routes.admin import get_mutation_stats, get_sync_stats
    from workspace_secretary.web.alerting import check_and_alert

    await asyncio.sleep(HEALTH_CHECK_INITIAL_DELAY_SECONDS)
    while True:
        try:
            mutation_stats = get_mutation_stats()
            sync_stats = get_sync_stats()

            overall_health = "healthy"
            if (
                mutation_stats["health"] == "critical"
                or sync_stats["health"] == "critical"
            ):
                overall_health = "critical"

            if overall_health == "critical":
                alerts_sent = check_and_alert(mutation_stats, sync_stats)
                if alerts_sent:
                    logger.warning(f"Critical alerts sent: {alerts_sent}")
        except Exception as e:
            logger.error(f"Health check error: {e}")

        await asyncio.sleep(HEALTH_CHECK_INTERVAL_SECONDS)


async def _init_shared_state():
    from workspace_secretary.engine.api import state, _init_connection_pool, try_enroll
    import asyncio
    
    enrolled = await try_enroll()
    if not enrolled:
        logger.warning("OAuth enrollment not complete - executor will wait for enrollment")
        return
    
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _init_connection_pool)
    logger.info(f"Shared IMAP pool initialized with {state._imap_pool_size} connections")


async def _executor_loop():
    from workspace_secretary.executor.imap_executor import run_forever, ExecutorConfig
    
    try:
        await run_forever(ExecutorConfig())
    except asyncio.CancelledError:
        logger.info("Executor loop cancelled")
    except Exception as e:
        logger.exception(f"Executor loop crashed: {e}")


@asynccontextmanager
async def lifespan(app):
    global _executor_task
    
    await _init_shared_state()
    
    health_check_task = asyncio.create_task(_health_check_loop())
    logger.info("Background health check started")
    
    _executor_task = asyncio.create_task(_executor_loop())
    logger.info("Background job executor started")
    
    yield
    
    if _executor_task:
        _executor_task.cancel()
        try:
            await _executor_task
        except asyncio.CancelledError:
            pass
        logger.info("Background job executor stopped")
    
    health_check_task.cancel()
    try:
        await health_check_task
    except asyncio.CancelledError:
        pass
    logger.info("Background health check stopped")


web_app = FastAPI(
    title="Secretary Web",
    description="AI-powered email client",
    docs_url="/api/docs",
    redoc_url=None,
    lifespan=lifespan,
)


def init_web_app(config: Optional[WebConfig] = None):
    global _web_config
    _web_config = config

    from workspace_secretary.web.auth import init_auth, router as auth_router
    from workspace_secretary.web.routes.tasks import router as tasks_router
    from workspace_secretary.web.engine_client import get_engine_url

    from workspace_secretary.web.auth import CSRFMiddleware

    engine_url = get_engine_url()
    if _running_in_docker() and any(
        host in engine_url for host in ("localhost", "127.0.0.1")
    ):
        logger.warning(
            "ENGINE_API_URL points to localhost in Docker; use the engine service name instead."
        )

    init_auth(config)
    web_app.include_router(auth_router)
    web_app.include_router(tasks_router)

    web_app.add_middleware(CSRFMiddleware)

    web_app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    logger.info("Web app initialized")


def get_web_config() -> Optional[WebConfig]:
    return _web_config


def get_template_context(request: Request, **kwargs) -> dict:
    from workspace_secretary.web.auth import CSRF_COOKIE, get_session
    from workspace_secretary.web.database import get_pool
    import json

    session = get_session(request)
    theme = "dark"
    density = "default"

    if session:
        try:
            pool = get_pool()
            with pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT prefs_json FROM user_preferences WHERE user_id = %s",
                        (session.user_id,),
                    )
                    row = cur.fetchone()
                    if row:
                        prefs = json.loads(row[0])
                        theme = prefs.get("theme", theme)
                        density = prefs.get("density", density)
        except Exception:
            pass

    if _web_config and _web_config.theme:
        theme = _web_config.theme

    csrf_token = request.cookies.get(CSRF_COOKIE)

    # Auto-detect current page from URL path for nav highlighting
    path = request.url.path.strip("/").split("/")[0] if request.url.path else ""
    current_page = path if path else "inbox"
    # Map some paths to their canonical nav names
    page_mapping = {
        "": "inbox",
        "thread": "inbox",
        "compose": "inbox",
        "dashboard": "inbox",
        "admin": "settings",
    }
    current_page = page_mapping.get(current_page, current_page)

    return {
        "request": request,
        "theme": theme,
        "density": density,
        "session": session,
        "user_name": session.name if session else None,
        "user_email": session.email if session else None,
        "csrf_token": csrf_token,
        "current_page": current_page,
        **kwargs,
    }


@web_app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return RedirectResponse(url="/inbox")


@web_app.get("/favicon.ico")
async def favicon():
    return Response(content=b"", media_type="image/x-icon")


@web_app.get("/health")
async def health():
    return {"service": "secretary-web", "healthy": True}
