from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from bson import ObjectId


@dataclass
class Task:
    title: str
    status: str = "pending"  # pending | done
    description: Optional[str] = None
    due_at: Optional[datetime] = None
    reminders: list[datetime] = field(default_factory=list)
    recurrence: Optional[str] = None  # "daily" | "weekly:mon,wed" | None
    created_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    def to_dict(self) -> dict:
        d = {
            "title": self.title,
            "status": self.status,
            "description": self.description,
            "due_at": self.due_at,
            "reminders": self.reminders,
            "recurrence": self.recurrence,
            "created_at": self.created_at,
        }
        if self._id:
            d["_id"] = self._id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Task":
        return cls(
            _id=d.get("_id"),
            title=d["title"],
            status=d.get("status", "pending"),
            description=d.get("description"),
            due_at=d.get("due_at"),
            reminders=d.get("reminders", []),
            recurrence=d.get("recurrence"),
            created_at=d.get("created_at", datetime.utcnow()),
        )


@dataclass
class Routine:
    name: str
    time: str        # "HH:MM" in user's timezone
    days: list[str]  # ["mon","tue","wed","thu","fri","sat","sun"]
    items: list[str]
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    def to_dict(self) -> dict:
        d = {
            "name": self.name,
            "time": self.time,
            "days": self.days,
            "items": self.items,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }
        if self._id:
            d["_id"] = self._id
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Routine":
        return cls(
            _id=d.get("_id"),
            name=d["name"],
            time=d["time"],
            days=d.get("days", ["mon","tue","wed","thu","fri","sat","sun"]),
            items=d.get("items", []),
            enabled=d.get("enabled", True),
            created_at=d.get("created_at", datetime.utcnow()),
        )
