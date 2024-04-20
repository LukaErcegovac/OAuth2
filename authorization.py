from fastapi import FastAPI, HTTPException
from pymongo import MongoClient
from datetime import datetime, timedelta
from jose import jwt
from pydantic import BaseModel
from dotenv import load_dotenv
from pymongo.errors import ConnectionFailure
import os
import bcrypt
import asyncio
import httpx
import sys

app = FastAPI()

load_dotenv()

MONGO_DB = os.getenv("MONGO_DB")
MONGO_CONNECTION_STRING = os.getenv("MONGO_CONNECTION_STRING")
client = MongoClient(MONGO_CONNECTION_STRING)
db = client[MONGO_DB]
users_collection = db["Users"]

SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = os.getenv("ALGORITHM")
ACCESS_TOKEN_EXPIRE_MINUTES = 30

client = None

class User(BaseModel):
    email: str
    full_name: str
    address: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

async def connect_to_mongodb():
    global client
    try:
        client = MongoClient(MONGO_CONNECTION_STRING)
        client.server_info()
    except ConnectionFailure:
        raise HTTPException(status_code=500, detail="Could not connect to MongoDB")

async def send_heartbeat():
    server_port = get_local_port()

    while True:
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post('http://localhost:8000/heartbeat', json={"server_port": server_port})
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

def verify_password(plain_password, hashed_password):
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password)

def get_password_hash(password):
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

def create_access_token(data: dict, expires_delta: timedelta):
    to_encode = data.copy()
    expire = datetime.utcnow() + expires_delta
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt

async def register(user: User):
    try:
        if users_collection.find_one({"email": user.email}):
            raise HTTPException(status_code=400, detail="User already exists")

        hashed_password = get_password_hash(user.password)

        user_dict = user.dict()
        user_dict["password"] = hashed_password
        user_dict["role"] = "user"

        users_collection.insert_one(user_dict)

        return {"message": "User registered successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to register user: {str(e)}")
    
async def login(userlogin: UserLogin):
    try:
        email = userlogin.email
        password = userlogin.password

        user = users_collection.find_one({"email": email})

        if not user or not verify_password(password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid email or password")

        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"email": email, "role": user["role"]}, expires_delta=access_token_expires
        )

        print(access_token)

        return {"access_token": access_token, "token_type": "bearer"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Login failed: {str(e)}")



@app.on_event("startup")
async def startup_event():
    await connect_to_mongodb()
    print("Connected to MongoDB")
    asyncio.create_task(send_heartbeat())
    

@app.on_event("shutdown")
async def shutdown_event():
    if client:
        client.close()
        print("MongoDB connection closed")

@app.post("/register")
async def register_user(user: User):
   return await register(user)

@app.post("/login")
async def login_user(userlogin: UserLogin):
   return await login(userlogin)
