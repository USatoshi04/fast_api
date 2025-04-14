from decouple import config
from typing import Union
from fastapi import HTTPException
import motor.motor_asyncio
from bson import ObjectId
from auth_utils import AuthJwtCsrf

MONGO_API_KEY = config("MONGO_API_KEY")

# グローバル変数の初期化
client = None
database = None
collection_todo = None
collection_user = None
auth = AuthJwtCsrf()

async def connect_to_mongo():
    """アプリケーション起動時に呼び出す接続初期化関数"""
    global client, database, collection_todo, collection_user
    # シンプルな接続設定
    client = motor.motor_asyncio.AsyncIOMotorClient(MONGO_API_KEY)
    database = client.API_DB
    collection_todo = database.todo
    collection_user = database.user
    
    # 接続テスト - これにより初期化が確実に行われる
    await database.command('ping')
    print("MongoDB接続が確立されました")

async def close_mongo_connection():
    """アプリケーション終了時に呼び出す接続クローズ関数"""
    global client
    if client:
        client.close()
        print("MongoDB接続を閉じました")

# 以下、他の関数は変更なし
def todo_serializer(todo) -> dict:
    return {
        "id": str(todo["_id"]),
        "title": todo["title"],
        "description": todo["description"],
    }

def user_serializer(user) -> dict:
    return {
        "id": str(user["_id"]),
        "email": user["email"]
    }

async def db_create_todo(data: dict) -> Union[dict, bool]:
    todo = await collection_todo.insert_one(data)
    new_todo = await collection_todo.find_one({"_id": todo.inserted_id})
    if new_todo:
        return todo_serializer(new_todo)
    return False

async def db_get_todos() -> list:
    todos = []
    for todo in await collection_todo.find().to_list(length=100):
        todos.append(todo_serializer(todo))
    return todos


async def db_get_single_todo(id: str) -> Union[dict, bool]:
    todo = await collection_todo.find_one({"_id": ObjectId(id)})
    if todo:
        return todo_serializer(todo)
    return False


async def db_update_todo(id: str, data: dict) -> Union[dict, bool]:
    todo = await collection_todo.find_one({"_id": ObjectId(id)})
    if todo:
        updated_todo = await collection_todo.update_one(
            {"_id": ObjectId(id)}, {"$set": data}
        )
        if (updated_todo.modified_count > 0):
            new_todo = await collection_todo.find_one({"_id": ObjectId(id)})
            return todo_serializer(new_todo)
    return False


async def db_delete_todo(id: str) -> bool:
    todo = await collection_todo.find_one({"_id": ObjectId(id)})
    if todo:
        deleted_todo = await collection_todo.delete_one({"_id": ObjectId(id)})
        if (deleted_todo.deleted_count > 0):
            return True
        return False

async def db_signup(data: dict) -> dict:
    email = data.get("email")
    password = data.get("password")
    overlap_user = await collection_user.find_one({"email": email})
    if overlap_user:
        raise HTTPException(status_code=400, detail="Email already exists")
    if not password or len(password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = await collection_user.insert_one({"email": email, "password": auth.generate_hashed_pw(password)})
    new_user = await collection_user.find_one({"_id": user.inserted_id})
    return user_serializer(new_user)

async def db_login(data: dict) -> str:
    email = data.get("email")
    password = data.get("password")
    user = await collection_user.find_one({"email": email})
    if not user or not auth.verify_pw(password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    return auth.encode_jwt(user["email"])
