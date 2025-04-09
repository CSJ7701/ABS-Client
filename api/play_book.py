
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class BookChapter:
    id: int
    start: float
    end: float
    title: str

    @classmethod
    def from_dict(cls, data: dict) -> "BookChapter":
        return cls(
            id = int(data.get("id", 0)),
            start = float(data.get("start", 0.0)),
            end = float(data.get("end", 0.0)),
            title = data.get("title", "Unknown"),
        )

@dataclass
class AudioFile:
    index: int
    start_offset: float
    duration: float
    url: str
    bytes: int

    @classmethod
    def from_dict(cls, data: dict) -> "AudioFile":
        _metadata = data.get("metadata", {})
        return cls(
            index = int(data.get("index", 0)),
            start_offset = float(data.get("start_offset", 0.0)),
            duration = float(data.get("duration", 0.0)),
            url = data.get("contentUrl", ""),
            bytes = _metadata.get("bytes", 0)
            )

@dataclass
class PlayBook:
    id: str
    libraryItemId: str
    title: str
    author: str
    duration: float
    chapter_count: int
    cover_path: str
    chapters_metadata: List[BookChapter]
    media_files: List[AudioFile]
    startTime: float
    currentTime: float
    updatedAt: int

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id = data["id"],
            libraryItemId = data["libraryItemId"],
            title = data.get("displayTitle", "Unknown"),
            author = data.get("displayAuthor", "Unknown"),
            duration = float(data.get("duration", 0.0)),
            cover_path = "",
            chapter_count = len(data.get("chapters", [])),
            chapters_metadata = [
                BookChapter.from_dict(ch) for ch in data.get("chapters", [])
                   ],
            media_files = [
                AudioFile.from_dict(f) for f in data.get("audioTracks", [])
                   ],
            startTime = float(data.get("startTime", 0.0)),
            currentTime = float(data.get("currentTime", 0.0)),
            updatedAt = int(data.get("updatedAt", 0)),
        )




