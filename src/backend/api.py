import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.backend.runner import SimulationRunner

# Global single instance wrapper
runner = SimulationRunner()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup
    yield
    # Teardown
    runner.pause()

app = FastAPI(title="FreqBridge API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/start")
async def start_sim():
    runner.start()
    return {"status": "started"}

@app.post("/pause")
async def pause_sim():
    runner.pause()
    return {"status": "paused"}

@app.post("/reset")
async def reset_sim():
    runner.reset()
    return {"status": "reset"}

@app.post("/inject/cloud")
async def inject_cloud():
    runner.inject_cloud_shock()
    return {"status": "cloud shock injected"}

@app.post("/inject/wind")
async def inject_wind():
    runner.inject_wind_collapse()
    return {"status": "wind shock injected"}

@app.post("/switch/pid")
async def switch_pid():
    runner.switch_pid()
    return {"status": "switched to pid baseline"}

@app.get("/state")
async def get_state():
    return runner.get_frontend_state()

# Provide stub endpoints mapped to /state subsets for compatibility if needed
@app.get("/metrics")
async def get_metrics():
    return runner.get_frontend_state().get("kpis")

@app.get("/topology")
async def get_topology():
    return runner.get_frontend_state().get("topology")

@app.get("/logs")
async def get_logs():
    return {"logs": runner.logs}

# WEBSOCKET
active_connections = []

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            # Send state at 2 Hz
            state_data = runner.get_frontend_state()
            await websocket.send_text(json.dumps(state_data))
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        active_connections.remove(websocket)
    except Exception as e:
        if websocket in active_connections:
            active_connections.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.backend.api:app", host="0.0.0.0", port=8000, reload=True)
