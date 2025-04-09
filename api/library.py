from dataclasses import dataclass
from typing import List

@dataclass
class Library:
    id: str
    name: str
    media_type: str
    provider: str

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            id=data["id"],
            name=data["name"],
            media_type=data["mediaType"],
            provider=data["provider"]
        )

@dataclass
class LibraryItem:
    id: str
    title: str
    author: str
    genre: List[str]
    series: str
    cover_path: str

    @classmethod
    def from_dict(cls, data: dict):
        metadata = data.get("media", {}).get("metadata", {})
        return cls(
            id=data["id"],
            title=metadata.get("title", "Unknown Title"),
            author=metadata.get("authorName", "Unknown Author"),
            genre=metadata.get("genres"),
            series=metadata.get("seriesName"),
            cover_path=""
        )

    
