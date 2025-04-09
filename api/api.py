import time
from typing import Callable, Dict, List, Optional
import httpx
from pathlib import Path
import os
import threading
import hashlib
import queue

from api.book import Book
from api.play_book import PlayBook
from api.session import Session

from .library import Library, LibraryItem

class API:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.player = None
        self.token = None
        self.client = httpx.Client()
        self.sessions:List[Session] = []
        self.current_session = None


        cache_home = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
        self.data_dir = Path(cache_home)/"AudiobookShelfClient"
        self.cover_cache_dir = self.data_dir / 'covers'
        self.audio_cache_dir = self.data_dir / 'audio'
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.cover_cache_dir.mkdir(parents=True, exist_ok=True)
        self.audio_cache_dir.mkdir(parents=True, exist_ok=True)

        self.max_cache_size_gb = 4
        self.cache_expiry_days = 30 # Cache files expire after 30 days

        self.sync_timer = None
        self.min_listen_threshold = 30 # Minimum seconds to consider "worth" syncing


    def set_base_url(self, base_url: str):
        self.base_url = base_url.rstrip("/")

    def set_player(self, player):
        self.player = player

    def set_token(self, token: str):
        self.token = token

    def request(self, method: str, endpoint: str, **kwargs):
        """Make an API request with authentication."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})

        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        try:
            response =  self.client.request(method, url, headers=headers, **kwargs)
            return response.json()
        except httpx.HTTPStatusError as e:
            print(f"API Error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"Network Error: {e}")
        return None

    def raw_request(self,method: str, endpoint: str, **kwargs) -> Optional[httpx.Response]:
        """Make an API request that returns the raw response (for binary data)."""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        headers = kwargs.pop("headers", {})
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        try:
            response = self.client.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            print(f"API Error: {e.response.status_code} - {e.response.text}")
        except httpx.RequestError as e:
            print(f"Network Error: {e}")
        return None

    def stream_request(self, endpoint: str) -> Optional[httpx.Response]:
        try:
            url = f"{self.base_url}/{endpoint.lstrip('/')}"
            response = self.client.get(url, headers=self.get_auth_headers(), follow_redirects=True)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as e:
            print(f"API Error: {e.response.status_code} - {e.response.text}")
            raise
        except httpx.RequestError as e:
            print(f"Network Error: {e}")
            raise

    def login(self, username: str, password: str) -> bool:
        """Perform login and store token asynchronously."""
        data = {"username": username, "password": password}
        response =  self.request("POST", "login", json=data)

        if response and "user" in response:
             self.set_token(response["user"]["token"])
             return True
        return False

    def get_auth_headers(self):
        if not self.token:
            raise ValueError("Not authenticated.")
        return {"Authorization": f"Bearer {self.token}"}    

    def libraries(self) -> Dict[str,Library]:
        response =  self.request("GET", "api/libraries", headers=self.get_auth_headers())

        if response and "libraries" in response:
            return {lib["name"]: Library.from_dict(lib) for lib in response["libraries"]}
        else:
            raise ValueError("No known libraries.")

    def library_items(self, library_id: str) -> List[LibraryItem]:
        response = self.request("GET", f"api/libraries/{library_id}/items", headers=self.get_auth_headers())

        if response and "results" in response:
            return [LibraryItem.from_dict(item) for item in response["results"]]
        else:
            raise ValueError("No items found in library.")

    def book_details(self, book_id: str) -> Book:
        response = self.request("GET", f"api/items/{book_id}?expanded=1&include=progress", headers=self.get_auth_headers())
        if response:
            detail = Book.from_dict(response)
            detail.cover_path = self.download_cover(book_id)
            return detail
        else:
            raise ValueError("No book found.")
            

    def _get_cover_path(self, cover_id: str) -> Path:
        return self.cover_cache_dir/f"{cover_id}.jpg"

    def _get_audio_path(self, cache_key: str) -> Optional[Path]:
        """Check if audio file exists in cache and is valid."""
        cache_path = self.audio_cache_dir / f"{cache_key}.mp3"

        if cache_path.exists():
            file_age = time.time() - cache_path.stat().st_mtime
            if file_age < (self.cache_expiry_days * 24 * 60 * 60):
                return cache_path

        return None

    def _get_file_cache_key(self, book_title: str, file_index: int) -> str:
        """Generate a stable cache key from book title and file index."""
        title_hash = hashlib.md5(book_title.encode('utf-8')).hexdigest()
        return f"{title_hash}_{file_index}"

    def download_cover(self, item_id: str) -> str:
        cover_path = self._get_cover_path(item_id)
        if cover_path.exists():
            return str(cover_path)

        cover_url = f"api/items/{item_id}/cover"
        response = self.raw_request("GET", cover_url, headers=self.get_auth_headers())
        if response and response.status_code == 200:
            try:
                if not response.headers.get('content-type', '').startswith('image/'):
                    print(f"Warning: Downloaded content is not an image: {response.headers.get('content-type')}")

                with open(cover_path, 'wb') as file:
                    file.write(response.content)

                if cover_path.exists() and cover_path.stat().st_size > 0:
                    return str(cover_path)
                else:
                    print(f"Error: Cover file wasn't created properly at {cover_path}")
                    return ""
            except Exception as e:
                print(f"Error saving cover image: {e}")
                if cover_path.exists():
                    cover_path.unlink()
                return ""
        else:
            print(f"Error downloading cover for item {item_id}")
            return ""

    def download_audio(self, cache_key: str, url: str, progress_callback: Optional[Callable[[int,int], None]] = None) -> Optional[Path]:
        """Download and cache an audio file, returning the path if successful."""
        cache_path = self.audio_cache_dir / f"{cache_key}.mp3"
                       
        existing = self._get_audio_path(cache_key)
        if existing:
            return existing
        response = self.stream_request(url)
        if not response:
            return None
        try:
            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            with open(cache_path, 'wb') as f:
                for chunk in response.iter_bytes(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback and total_size > 0:
                            progress_callback(downloaded, total_size)
            self._cleanup_cache_if_needed()
            return cache_path
        except Exception as e:
            print(f"Error caching audio file: {e}")
            if cache_path.exists():
                cache_path.unlink()
            return None

    def get_cover(self, item_id: str) -> str:
        """Get a cover image, either from cache or by downloading."""
        cover_path = self._get_cover_path(item_id)

        if cover_path.exists():
            return str(cover_path)
        return self.download_cover(item_id)

    def in_progress(self):
        url = "api/me/items-in-progress"
        response = self.request("GET", url, headers=self.get_auth_headers())
        if response and "libraryItems" in response:
            in_progress = []
            items = response.get("libraryItems")
            for item in items:
                in_progress.append(item.get("id"))

            return in_progress
        return None

    def _cleanup_cache_if_needed(self):
        """Clean up old cache files if total size exceeds limit."""
        try:
            total_size = sum(f.stat().st_size for f in self.audio_cache_dir.glob('*') if f.is_file())
            max_bytes = self.max_cache_size_gb * 1024 * 1024 * 1024

            if total_size > max_bytes:
                files = sorted(
                    [f for f in self.audio_cache_dir.glob('*') if f.is_file()],
                    key = lambda x: x.stat().st_mtime
                )

                for file in files:
                    if total_size <= max_bytes * 0.9:
                        break

                    file_size = file.stat().st_size
                    file.unlink()
                    total_size -= file_size
                    print(f"Removed {file.name} from cache to free space.")
        except Exception as e:
            print(f"Error cleaning up cache: {e}")

    def play_item(self, item_id: str, episode_id: Optional[str] = None) -> Optional[PlayBook]:
        if self.current_session:
            self.sync_session(self.current_session, getattr(self, 'player', None))
            
        endpoint = f"api/items/{item_id}/play"
        if episode_id:
            endpoint = f"api/items/{item_id}/play/{episode_id}"

        payload = {
            "deviceInfo": {"clientVersion": "0.0.1"},
            "supportedMimeTypes": ["audio/flac", "audio/mpeg", "audio/mp4"]
        }
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"

        response = self.request("POST", endpoint, headers=headers, json=payload)
        #print(response)

        if response:
            try:
                book = PlayBook.from_dict(response)
                book.cover_path = self.get_cover(item_id)
                
                new_session = Session.from_dict(response)
                self.sessions.append(new_session)
                self.current_session = new_session

                self.start_sync_timer()
                
                return book
            except Exception as e:
                print(f"Error playing book: {e}")
        return None

    def close_session(self, session_id: str):
        endpoint = f"api/session/{session_id}/close"

        ## payload = {
        ##     "currentTime": 
        ##     "timeListened": 0,
        ##     }
        payload = {}

        headers = self.get_auth_headers()
        headers['Content-Type'] = "application/json"

        try:
            self.raw_request("POST", endpoint, headers=headers, json=payload)
        except Exception as e:
            print(f"Error closing session {session_id}: {e}")

        return

    def sync_session(self, session:Session, player=None):
        """
        Sync the session with the server.
        If player is provided, update the session with current playback information first.
        """
        if player and player.book and player.book.libraryItemId == session.libraryItemId:
            current_time = time.time()

            time_elapsed = current_time - (session.updatedAt/1000) if session.updatedAt > 0 else 0

            if player.is_playing() and time_elapsed >= self.min_listen_threshold:
                session.timeListening += time_elapsed

            # Always update current position
            session.currentTime = player.global_position
            session.updatedAt = int(current_time * 1000)
        
        endpoint = "api/session/local"
        payload = session.to_dict()
        headers = self.get_auth_headers()
        headers["Content-Type"] = "application/json"
        try:
            self.raw_request("POST", endpoint, headers=headers, json=payload)
            print(f"Synced session {session.id} (current time: {session.currentTime:.1f}s)")
            return True
        except Exception as e:
            print(f"Error syncing session {session.id} for {session.title}: {e}")
            return False

    def start_sync_timer(self):
        """Start a timer that periodically syncs the current session."""
        def sync_task():
            while True:
                time.sleep(5)
                self.sync_current_session()

        if self.sync_timer is None or not self.sync_timer.is_alive():
            self.sync_timer = threading.Thread(target=sync_task, daemon=True)
            self.sync_timer.start()

    def sync_current_session(self):
        """Sync the current active session, if one exists."""
        if not self.current_session or not hasattr(self, 'player'):
            return
            
        if self.player.book and self.player.book.libraryItemId == self.current_session.libraryItemId:
            # Initial buffer before we sync.
            if self.player.global_position > 0 and self.player.is_playing():
                self.sync_session(self.current_session, self.player)

                
            


        

                    

        
