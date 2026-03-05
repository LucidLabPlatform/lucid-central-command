"""lucid-cc FastAPI app with lifespan, MQTT bridge, and broadcaster."""
import asyncio
import logging
import queue
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

from app import db as DB
from app.broadcaster import Broadcaster
from app.mqtt_bridge import MqttBridge
from app.routes.api import router as api_router
from app.routes.ui import router as ui_router
from app.state import FleetState

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

_STATIC_DIR = os.path.join(os.path.dirname(__file__), "web", "static")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Init shared Postgres schema
    DB.init_schema()

    # Shared state
    event_queue: queue.Queue = queue.Queue(maxsize=10_000)
    ws_clients: set = set()
    fleet = FleetState()

    # MQTT bridge
    bridge = MqttBridge(event_queue)
    bridge.start()

    # Broadcaster task
    broadcaster = Broadcaster(event_queue, fleet, ws_clients)
    bc_task = asyncio.create_task(broadcaster.run())

    # Attach to app state
    app.state.fleet = fleet
    app.state.bridge = bridge
    app.state.ws_clients = ws_clients

    log.info("lucid-cc started")
    yield

    # Shutdown
    broadcaster.stop()
    bc_task.cancel()
    bridge.stop()
    log.info("lucid-cc stopped")


app = FastAPI(title="LUCID Central Command", lifespan=lifespan)

app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")
app.include_router(api_router, prefix="/api")
app.include_router(ui_router)
