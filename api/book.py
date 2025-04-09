
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class Book:
    id: str
    title: str
    author: str
    series: Optional[str]
    description: str
    genres: List[str]
    narrator: Optional[str]
    published_year: Optional[str]
    publisher: Optional[str]
    language: Optional[str]
    explicit: bool
    duration: float
    progress: float
    finished: bool
    cover_path: str

    @classmethod
    def from_dict(cls, data: dict):
        _metadata = data.get("media", {}).get("metadata", {})
        _progress = data.get("userMediaProgress", {})
        return cls(
            id=data["id"],
            title=_metadata.get("title", "Unknown Title"),
            author=_metadata.get("authorName", "Unknown Author"),
            series=_metadata.get("seriesName"),
            description=_metadata.get("description", ""),
            genres=_metadata.get("genres", []),
            narrator=_metadata.get("narratorName"),
            published_year=_metadata.get("publishedYear"),
            publisher=_metadata.get("publisher"),
            language=_metadata.get("language"),
            explicit=_metadata.get("explicit", False),
            duration=_progress.get("duration"),
            progress=_progress.get("progress"),
            finished=_progress.get("isFinished"),
            cover_path=""  # You can set this later
        )
    
