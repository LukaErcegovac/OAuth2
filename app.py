from fastapi import FastAPI
from pydantic import BaseModel
import time

app = FastAPI()

SIDE_SERVERS = {}
server_counter = 0
HEARTBEAT_TIMEOUT = 60  # Timeout in seconds

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


@app.get('/servers')
async def get_servers():
    return SIDE_SERVERS


def cleanup_servers():
    current_time = int(time.time())
    global server_counter

    for server_name, server_info in list(SIDE_SERVERS.items()):
        if current_time - server_info["timestamp"] > HEARTBEAT_TIMEOUT:
            print(f"Server {server_name} timed out and removed from the list.")
            del SIDE_SERVERS[server_name]
            server_counter -= 1