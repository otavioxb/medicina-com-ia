import os
import asyncio
from dotenv import load_dotenv
from fastapi import FastAPI
from contextlib import asynccontextmanager
from redis import asyncio as aioredis
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.requests import Request

from app.routers import auth_routes, websocket as ws_router, cadastro_routes, transcription_routes, download_relatorio_routes, dashboard_routes
from app.db.init_db import create_tables

load_dotenv()

REDIS_URL = os.getenv("REDIS_BROKER_URL", "redis://localhost:6379/0")

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.redis = aioredis.from_url(REDIS_URL, decode_responses=True)

    app.state.ws_timeout_task = asyncio.create_task(ws_router.verificar_timeouts())

    try:
        yield
    finally:
        task = app.state.ws_timeout_task
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        await app.state.redis.close()

app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

create_tables()

app.include_router(auth_routes.router)
app.include_router(ws_router.router)
app.include_router(cadastro_routes.router)
app.include_router(transcription_routes.router)
app.include_router(download_relatorio_routes.router)
app.include_router(dashboard_routes.router)

app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/static/html")


@app.get("/dashboard", response_class=HTMLResponse)
def render_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "5000"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=True)
