from dataclasses import dataclass
from typing import Optional
from uuid import UUID

@dataclass
class Session:
    id: str
    userId: str
    libraryId: str
    libraryItemId: str
    timeListening: float
    startTime: float
    currentTime: float
    updatedAt: int

    title: str

    @classmethod
    def from_dict(cls, data:dict):
        return cls(
            id = data["id"],
            userId = data["userId"],
            libraryId = data["libraryId"],
            libraryItemId = data["libraryItemId"],
            timeListening = data.get("timeListening", 0.0),
            startTime = data.get("startTime", 0.0),
            currentTime = data.get("currentTime", 0.0),
            updatedAt = data.get("updatedAt", 0),
            title = data.get("displayTitle", "Unknown")
            )

    def to_dict(self):
        return {
            "id": self.id,
            "userId": self.userId,
            "libraryId": self.libraryId,
            "libraryItemId": self.libraryItemId,
            "timeListening": self.timeListening,
            "startTime": self.startTime,
            "currentTime": self.currentTime,
            "updatedAt": self.updatedAt
        }
    
    
