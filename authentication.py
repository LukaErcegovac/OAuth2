from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from pymongo.errors import ConnectionFailure
from pymongo import MongoClient
from dotenv import load_dotenv
from jose import jwt, JWTError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import httpx
from typing import List
import asyncio
import sys
import os

app = FastAPI()
security = HTTPBearer()

load_dotenv()

MONGO_DB = os.getenv("MONGO_DB")
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
client = MongoClient(MONGO_CONNECTION_STRING)
db = client[MONGO_DB]
data_collection = db["Data"]

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")

class Item(BaseModel):
    name: str
    description: str

async def connect_to_mongodb():
    global client
    try:
        client = MongoClient(MONGO_CONNECTION_STRING)
        client.server_info()
    except ConnectionFailure:
        raise HTTPException(status_code=500, detail="Could not connect to MongoDB")
    
async def send_heartbeat():
    server_port = get_local_port()
    auth = "authentication"

    while True:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post('http://localhost:8000/heartbeat', json={"server_port": server_port, "auth": auth})
                print(response.text)
            except httpx.HTTPError as exc:
                print(f"HTTP error occurred: {exc}")
            except Exception as exc:
                print(f"Error occurred: {exc}")
        await asyncio.sleep(3) 

def get_local_port():    
    if "--port" in sys.argv:
                index = sys.argv.index("--port")
                port = int(sys.argv[index + 1])
    return port

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate credentials")

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    if not token:
        raise HTTPException(status_code=401, detail="Token missing")
    return decode_token(token)

def get_user_role(token: str = Depends(verify_token)):
    user_role = token.get("role")
    if not user_role:
        raise HTTPException(status_code=403, detail="User role not found in token")
    return user_role

def save_item(item: Item):
    item_dict = item.dict()
    result = data_collection.insert_one(item_dict)
    return {"id": str(result.inserted_id)}



@app.on_event("startup")
async def startup_event():
    await connect_to_mongodb()
    print("Connected to MongoDB")
    asyncio.create_task(send_heartbeat())

@app.post("/items", response_model=dict)
async def create_item(item: Item, token_data: dict = Depends(verify_token)):
    return save_item(item)

@app.get("/items", response_model= List[Item])
async def get_all_items(token_data: dict = Depends(verify_token)):
    items = data_collection.find() 
    return [Item(**item) for item in items]

@app.get("/protected")
async def protected_route(token_data: dict = Depends(verify_token)):
    return {"message": "This is a protected route", "token_data": token_data}

@app.get("/admin_only")
async def admin_only_route(user_role: str = Depends(get_user_role)):
    if user_role != "admin":
        raise HTTPException(status_code=403, detail="You need to be an admin to access this resource")
    return {"message": "Welcome, admin!"}

