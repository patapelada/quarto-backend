import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from quarto_backend.game.agent_handler import AgentHandler

app = FastAPI()

allowed_origins = os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def read_root():
    return {"Hello": "World"}


@app.get("/agent")
async def read_agent():
    agent = os.getenv("AGENT_ENDPOINT", None)
    if not agent:
        return {"error": "Agent endpoint not configured"}
    handler = AgentHandler(endpoint=agent)
    try:
        await handler.initialize()
        return {"identifier": handler.identifier, "endpoint": handler.endpoint}
    except RuntimeError as e:
        return {"error": str(e)}
