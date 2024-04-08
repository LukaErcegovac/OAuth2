from fastapi import FastAPI
import asyncio
import httpx
from uvicorn.config import Config
from uvicorn.main import Server

app = FastAPI()

MAIN_SERVER_URL = "http://localhost:8000"
PORT = 8000

async def check_main_server():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(MAIN_SERVER_URL)
            return response.status_code == 200
    except Exception:
        return False

async def start_secondary_server():
    print("Starting a new instance of the server...")
    config = Config(app="app:app", host="localhost", port=PORT)
    server = Server(config)
    await server.serve()

async def monitor_main_server():
    while True:
        if not await check_main_server():
            await start_secondary_server()
        await asyncio.sleep(2)

@app.on_event("startup")
async def startup():
    print("Server is starting...")
    asyncio.create_task(monitor_main_server())