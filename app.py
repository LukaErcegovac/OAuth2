from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import time
import random
import httpx

app = FastAPI()

SIDE_SERVERS = {}
server_counter = 0
HEARTBEAT_TIMEOUT = 60 

class User(BaseModel):
    email: str
    full_name: str
    address: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class HeartbeatData(BaseModel):
    server_port: int

@app.post("/heartbeat")
async def heartbeat(data: HeartbeatData):
    global server_counter

    server_port = data.server_port
    server_name = next((name for name, info in SIDE_SERVERS.items() if info["server_port"] == server_port), None)

    if server_name:
        SIDE_SERVERS[server_name]["timestamp"] = int(time.time())
        print(f"Heartbeat received from existing Server {server_name}. Updated timestamp at {time.ctime()}")
        cleanup_servers()
        return {
            "message": f"Heartbeat received from existing Server {server_name}. Updated timestamp",
            "current_servers": SIDE_SERVERS
        }
    else:
        server_name = f"server{server_counter + 1}"
        SIDE_SERVERS[server_name] = {
            "server_port": server_port,
            "timestamp": int(time.time())
        }
        server_counter += 1
        print(f"Heartbeat received from new Server {server_name} at {time.ctime()}")
        cleanup_servers()
        return {
            "message": f"Heartbeat received from new Server {server_name} and added to the list",
            "current_servers": SIDE_SERVERS
        }
    
async def register(user: User):
    try:
        server_name, server_info = random.choice(list(SIDE_SERVERS.items()))
        server_port = server_info["server_port"]

        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://localhost:{server_port}/register", json=user.dict())
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(exc)}")
    
async def login(userlogin: UserLogin):
    try:
        server_name, server_info = random.choice(list(SIDE_SERVERS.items()))
        server_port = server_info["server_port"]

        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://localhost:{server_port}/login", json=userlogin.dict())
            response.raise_for_status()
            return response.json()

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to login user: {str(exc)}")


@app.get('/servers')
async def get_servers():
    return SIDE_SERVERS

@app.post('/register')
async def register_user(user: User):
    return await register(user)

@app.post('/login')
async def login_user(userlogin: UserLogin):
    return await login(userlogin)


def cleanup_servers():
    current_time = int(time.time())
    global server_counter

    for server_name, server_info in list(SIDE_SERVERS.items()):
        if current_time - server_info["timestamp"] > HEARTBEAT_TIMEOUT:
            print(f"Server {server_name} timed out and removed from the list.")
            del SIDE_SERVERS[server_name]
            server_counter -= 1