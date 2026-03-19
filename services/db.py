import os
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from models.schemas import Task, Routine

_client: AsyncIOMotorClient = None
_db = None


def get_db():
    return _db


async def connect():
    global _client, _db
    _client = AsyncIOMotorClient(os.environ["MONGO_URI"])
    _db = _client["discord_bot"]
    # Create indexes
    await _db.tasks.create_index("status")
    await _db.tasks.create_index("due_at")
    print("[DB] Connected to MongoDB Atlas")


async def disconnect():
    if _client:
        _client.close()


# --- Tasks ---

async def create_task(task: Task) -> Task:
    result = await _db.tasks.insert_one(task.to_dict())
    task._id = result.inserted_id
    return task


async def get_pending_tasks() -> list[Task]:
    cursor = _db.tasks.find({"status": "pending"}).sort("due_at", 1)
    return [Task.from_dict(d) async for d in cursor]


async def get_all_tasks() -> list[Task]:
    cursor = _db.tasks.find().sort("created_at", -1)
    return [Task.from_dict(d) async for d in cursor]


async def complete_task_by_title(title: str) -> bool:
    result = await _db.tasks.update_one(
        {"title": {"$regex": title, "$options": "i"}, "status": "pending"},
        {"$set": {"status": "done"}}
    )
    return result.modified_count > 0


async def delete_task_by_title(title: str) -> bool:
    result = await _db.tasks.delete_one(
        {"title": {"$regex": title, "$options": "i"}}
    )
    return result.deleted_count > 0


async def update_task_reminders(task_id: ObjectId, reminders: list) -> None:
    await _db.tasks.update_one(
        {"_id": task_id},
        {"$set": {"reminders": reminders}}
    )


# --- Routines ---

async def create_routine(routine: Routine) -> Routine:
    # Replace existing routine with same name
    await _db.routines.delete_one({"name": {"$regex": f"^{routine.name}$", "$options": "i"}})
    result = await _db.routines.insert_one(routine.to_dict())
    routine._id = result.inserted_id
    return routine


async def get_all_routines() -> list[Routine]:
    cursor = _db.routines.find()
    return [Routine.from_dict(d) async for d in cursor]


async def get_enabled_routines() -> list[Routine]:
    cursor = _db.routines.find({"enabled": True})
    return [Routine.from_dict(d) async for d in cursor]


async def delete_routine_by_name(name: str) -> bool:
    result = await _db.routines.delete_one(
        {"name": {"$regex": name, "$options": "i"}}
    )
    return result.deleted_count > 0


async def toggle_routine(name: str, enabled: bool) -> bool:
    result = await _db.routines.update_one(
        {"name": {"$regex": name, "$options": "i"}},
        {"$set": {"enabled": enabled}}
    )
    return result.modified_count > 0


# --- Settings (timezone etc) ---

async def get_setting(key: str, default=None):
    doc = await _db.settings.find_one({"key": key})
    return doc["value"] if doc else default


async def set_setting(key: str, value) -> None:
    await _db.settings.update_one(
        {"key": key},
        {"$set": {"value": value}},
        upsert=True
    )
