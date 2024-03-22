from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import time
import random
import httpx

app = FastAPI()
bearer_scheme = HTTPBearer()

SIDE_SERVERS = {}
AUTH_SIDE_SERVERS = {}
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
    auth: str | None = None

class Items(BaseModel):
    name: str
    description: str

@app.post("/heartbeat")
async def heartbeat(data: HeartbeatData):
    global server_counter

    server_port = data.server_port
    server_name = next((name for name, info in SIDE_SERVERS.items() if info["server_port"] == server_port), None)
    auth_server_name = next((name for name, info in AUTH_SIDE_SERVERS.items() if info["server_port"] == server_port), None)

    if data.auth:
        
        if auth_server_name:
            AUTH_SIDE_SERVERS[auth_server_name] = {
                "server_port": server_port,
                "timestamp": int(time.time())
            }
            print(f"Heartbeat received from authenticated Server {auth_server_name}. Updated timestamp at {time.ctime()}")
        else:
            auth_server_name = f"server{server_counter + 1}"
            AUTH_SIDE_SERVERS[auth_server_name] = {
                "server_port": server_port,
                "timestamp": int(time.time())
            }
            server_counter += 1
            print(f"Heartbeat received from new authenticated Server {auth_server_name} at {time.ctime()}")
    else:
      
        if server_name:
            SIDE_SERVERS[server_name] = {
                "server_port": server_port,
                "timestamp": int(time.time())
            }
            print(f"Heartbeat received from unauthenticated Server {server_name}. Updated timestamp at {time.ctime()}")
        else:
            server_name = f"server{server_counter + 1}"
            SIDE_SERVERS[server_name] = {
                "server_port": server_port,
                "timestamp": int(time.time())
            }
            server_counter += 1
            print(f"Heartbeat received from new unauthenticated Server {server_name} at {time.ctime()}")

    cleanup_servers()

    return {
        "message": f"Heartbeat received from Server {server_name}.",
        "current_servers": SIDE_SERVERS if not data.auth else AUTH_SIDE_SERVERS
    }

def cleanup_servers():
    current_time = int(time.time())
    global server_counter

    for server_name, server_info in list(SIDE_SERVERS.items()):
        if current_time - server_info["timestamp"] > HEARTBEAT_TIMEOUT:
            print(f"Server {server_name} timed out and removed from the list.")
            del SIDE_SERVERS[server_name]
            server_counter -= 1
    
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
    

async def post_item(data: Items, token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        server_name, server_info = random.choice(list(AUTH_SIDE_SERVERS.items()))
        server_port = server_info["server_port"]

        headers = {"Authorization": f"Bearer {token.credentials}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.post(f"http://localhost:{server_port}/items", json=data.dict(), headers=headers)
            response.raise_for_status() 
            return response.json()  

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to send data to worker server: {str(exc)}")


async def get_all_items(token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        server_name, server_info = random.choice(list(AUTH_SIDE_SERVERS.items()))
        server_port = server_info["server_port"]

        headers = {"Authorization": f"Bearer {token.credentials}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{server_port}/items", headers=headers)
            response.raise_for_status() 
            return response.json()  

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from worker server: {str(exc)}")
    
async def admin_only(token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    try:
        server_name, server_info = random.choice(list(AUTH_SIDE_SERVERS.items()))
        server_port = server_info["server_port"]

        headers = {"Authorization": f"Bearer {token.credentials}", "Content-Type": "application/json"}

        async with httpx.AsyncClient() as client:
            response = await client.get(f"http://localhost:{server_port}/admin_only", headers=headers)
            response.raise_for_status() 
            return response.json()  

    except httpx.HTTPStatusError as exc:
        raise HTTPException(status_code=exc.response.status_code, detail=exc.response.text)
    except httpx.RequestError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch data from worker server: {str(exc)}")

@app.get('/servers')
async def get_servers():
    return SIDE_SERVERS

@app.get('/auth_servers')
async def get_servers():
    return AUTH_SIDE_SERVERS

@app.post('/register')
async def register_user(user: User):
    return await register(user)

@app.post('/login')
async def login_user(userlogin: UserLogin):
    return await login(userlogin)    

@app.post("/items")
async def post_items(data: Items, token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return await post_item(data, token)


@app.get("/items")
async def get_all_items_from_auth(token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return await get_all_items(token)

@app.get("/admin_only")
async def admin_only_route(token: HTTPAuthorizationCredentials = Depends(bearer_scheme)):
    return await admin_only(token)