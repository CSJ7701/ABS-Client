
import queue
from api.api import API
import mpv
import time
import threading
import os
from typing import Optional, Callable, Dict, Tuple

from api.play_book import PlayBook
from api.play_book import BookChapter
from api.play_book import AudioFile

class Player:
    _instance = None
    def __new__(cls, api:Optional[API] = None):
        if cls._instance is None:
            cls._instance=super(Player,cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    def __init__(self, api:API):
        # Singleton
        if self._initialized:
            return
        self._initialized = True

        self.player = mpv.MPV(video=False, terminal=False, quiet=False)
        self.api: API = api
        self.book: Optional['PlayBook'] = None
        self.temp_dir: Optional[str] = None
        self.current_book_id: Optional[str] = None

        # State
        self.playing: bool = None
        self.paused: bool = None
        self.stop_requested: bool = False

        # Time tracking
        self.global_position: float = 0.0
        self.track_position: float = 0.0
        self.current_file_index: int = 0
        self.current_chapter_index: int = 1

        # Temp file tracking
        self.downloaded_files: Dict[str, Dict[int,str]] = {}
        self.download_queue = queue.Queue()
        self.is_downloading = False
        self.download_lock = threading.Lock()

        # Start the download worker
        self._start_download_worker()

        # Callbacks
        self.on_position_change: Optional[Callable[[float, int], None]] = None
        self.on_chapter_change: Optional[Callable[[int], None]] = None
        self.on_file_change: Optional[Callable[[int], None]] = None
        self.on_playback_end: Optional[Callable[[], None]] = None
        self.on_download_progress: Optional[Callable[[int, float], None]] = None

        # Background tasks
        self.position_thread: Optional[threading.Thread] = None
        self.preload_thread: Optional[threading.Thread] = None
        self.download_thread: Optional[threading.Thread] = None

        # Set default volume
        self.player.volume = 100

        self._handling_track_end = threading.Event()
        
        # Register event handlers
        @self.player.property_observer("eof-reached")
        def handle_end(_name, value):
            if value and self.playing:
                print("EOF detected by MPV (backup method)")
                threading.Thread(target=self._handle_track_end, daemon=True).start()

        @self.player.property_observer("idle-active")
        def handle_idle_change(_name, value):
            if value and self.playing and not self.paused:
                print("Player has become idle while playing - handling as track end")
                threading.Thread(target=self._handle_track_end, daemon=True).start()



    def set_player_bar(self, player_bar):
        """Set reference to PlayerBar for UI updates."""
        self.player_bar = getattr(self, 'player_bar', None)
        self.player_bar = player_bar
        

    def load_book(self, book: PlayBook) -> bool:
        """Load a book for playback."""

        try:
            if self.playing:
                self.stop()

            self.book = book
            self.current_book_id = book.id
            self.global_position = book.currentTime

            # Find current file and chapter based on position
            self.current_file_index, self.track_position = self._get_file_from_position(self.global_position)
            self.current_chapter_index = self._get_chapter_from_position(self.global_position)

            if self.current_book_id not in self.downloaded_files:
                self.downloaded_files[self.current_book_id] = {}

            # MUST set wait to true here.
            success = self._download_file(self.current_file_index, wait=True)
            if not success:
                print("Failed to download initial audio file.")
                return False

            # Preload the next file in the background
            #self._start_preload(self.current_file_index + 1)
            self._download_file(self.current_file_index + 1, wait=False)

            return True

        except Exception as e:
            print(f"Error loading book: {e}")
            return False


    def play(self) -> bool:
        """Start or resume playback"""
        try:
            if not self.book:
                print("No book loaded.")
                return False

            if hasattr(self, 'player_bar') and self.player_bar:
                self.player_bar.on_book_loaded(self.book)
                self.player_bar.update_play_button_state()
            
            if self.paused:
                self.player.pause = False
                self.paused = False
                self.playing = True

            # DONT PUT ANYTHING BETWEEN THESE TWO. YOU'LL BREAK PLAYBACK
            else:
                # Ensure current file is loaded
                file_path = None
                if self.current_book_id in self.downloaded_files:
                    file_path = self.downloaded_files[self.current_book_id].get(self.current_file_index)
                if not file_path:
                    print("Current file is not downloaded.")
                    return False

                play_event = threading.Event()
                play_success = [False]

                def play_thread_func():
                    try:

                        # Load file if not loaded
                        if not self.player.filename or self.player.filename != os.path.basename(file_path):
                            self.player.play(file_path)

                            load_start = time.time()
                            while time.time() - load_start < 1.0: # 5 second timeout
                                if self.player.idle is False:
                                    break
                                time.sleep(0.1)

                            if self.track_position > 0:
                                self.player.seek(self.track_position, reference="absolute")
                        self.player.pause = False
                        self._stop_requested = False
                        play_success[0] = True
                        play_event.set()
                    except Exception as e:
                        print(f"Error in play thread: {e}")
                        play_success[0] = False
                        play_event.set()

                play_thread = threading.Thread(target=play_thread_func)
                play_thread.daemon = True
                play_thread.start()

                if not play_event.wait(timeout=10.0):
                    print("Playback start timed out.")
                    return False

                if not play_success[0]:
                    print("Playback failed to start")
                    return False
                
                self.playing = True
                self.paused = False

                if not self.position_thread or not self.position_thread.is_alive():
                    self.position_thread = threading.Thread(target=self._track_position)
                    self.position_thread.daemon = True
                    self.position_thread.start()

                # print(f"Started playback at position {self.global_position:.2f}s")

            return True
        except Exception as e:
            print(f"Error playing: {e}")
            return False

    def pause(self) -> bool:
        """Pause playback"""
        try:
            # print(f"Playing: {self.playing} ; Paused: {self.paused}")
            if self.playing and not self.paused:
                self.player.pause = True
                self.paused = True
                return True

            print("Error pausing (not playing or already paused)")
            return False
        except Exception as e:
            print(f"Error pausing: {e}")
            return False

    def stop(self) -> bool:
        """Stop playback"""
        try:
            self._stop_requested = True
            self.player.stop()
            self.playing = False
            self.paused = False
            return True
        except Exception as e:
            print(f"Error stopping: {e}")
            return False

    def seek_to_position(self, position: float) -> bool:
        """Seek to a specific position in the audiobook (global position in seconds)"""
        try:
            if not self.book:
                print("No book loaded")
                return False

            if position < 0 or position > self.book.duration:
                print(f"Invalid position: {position} (book duration: {self.book.duration})")
                return False

            file_index, local_position = self._get_file_from_position(position)
            chapter_index = self._get_chapter_from_position(position)

            #print(f"Seeking to global position {position:.2f}s (File: {file_index}, Local: {local_position:.2f}s)")

            # Check if we need to switch to a different file 
            if file_index != self.current_file_index:
                #print(f"Seeking across files: {self.current_file_index} -> {file_index}")
                
                file_path = None
                if self.current_book_id in self.downloaded_files:
                    file_path = self.downloaded_files[self.current_book_id].get(file_index)
                    
                if not file_path:
                    print(f"Downloading file {file_index} for seek operation...")
                    success = self._download_file(file_index)
                    if not success:
                        print(f"Failed to download file for seek operation.")
                        return False
                    
                    file_path = self.downloaded_files[self.current_book_id].get(file_index)
                    if not file_path:
                        print(f"File downloaded, but path not available for file index {file_index}")
                        return False

                if not os.path.exists(file_path):
                    print(f"File exists in cache, but file not found: {file_path}")
                    success = self._download_file(file_index, wait=True)
                    if not success:
                        return False
                    file_path = self.downloaded_files[self.current_book_id].get(file_index)
                    if not file_path or not os.path.exists(file_path):
                        return False

                file_loaded = threading.Event()
                load_success = [False]
                
                def file_load_thread():
                    try:
                        print(f"Loading file: {file_path}")
                        self.player.play(file_path)
                        time.sleep(0.5)
                        load_success[0] = True
                        file_loaded.set()
                    except Exception as e:
                        print(f"Error loading file in seek operation: {e}")
                        load_success[0] = False
                        file_loaded.set()

                load_thread = threading.Thread(target=file_load_thread)
                load_thread.daemon = True
                load_thread.start()

                if not file_loaded.wait(timeout=10.0):
                    print("Timed out waiting for file to load during seek")
                    return False

                if not load_success[0]:
                    print("Failed to load file during seek operation.")
                    return False
                
                self.current_file_index = file_index

                # Preload the next file, and the previous one
                self._download_file(file_index + 1, wait=False)
                if file_index > 0:
                    self._download_file(file_index - 1, wait=False)

                if self.on_file_change:
                    self.on_file_change(file_index)

            # Seek within the current file
            # Make sure we have a valid position before seeking
            try:
                if local_position >= 0:
                    # print(f"Seeking to local position: {local_position:.2f}s")
                    self.player.seek(local_position, reference="absolute")
                else:
                    print(f"Invalid local position: {local_position}")
                    return False
            except Exception as e:
                print(f"Error during local seek: {e}")
                return False

            self.global_position = position
            self.track_position = local_position

            if chapter_index != self.current_chapter_index:
                self.current_chapter_index = chapter_index
                if self.on_chapter_change:
                    self.on_chapter_change(chapter_index)

            # print(f"Seeked to position: {position:.2f}s (File: {file_index}, Chapter: {chapter_index}, Local: {local_position:.2f}s)")
            return True
        except Exception as e:
            print(f"Error seeking: {e}")
            return False

    def seek_to_chapter(self, chapter_index: int) -> bool:
        """Seek to the beginning of a specific chapter"""
        try:
            if not self.book or not self.book.chapters_metadata:
                print("No book loaded or no chapter data available")
                return False
                
            if chapter_index < 1 or chapter_index > len(self.book.chapters_metadata):
                print(f"Invalid chapter index: {chapter_index}")
                return False
            
            # Get the global position for the start of this chapter
            position = self.book.chapters_metadata[chapter_index].start
            
            # Perform the seek
            return self.seek_to_position(position)
        except Exception as e:
            print(f"Error seeking to chapter: {e}")
            return False

    def next_chapter(self) -> bool:
        """Skip to the next chapter"""
        if not self.book:
            return False
            
        next_index = self.current_chapter_index + 1
        if next_index >= len(self.book.chapters_metadata):
            print("Already at the last chapter")
            return False
            
        return self.seek_to_chapter(next_index)
    
    def previous_chapter(self) -> bool:
        """Go back to the previous chapter or the start of the current chapter"""
        if not self.book:
            return False
            
        # If we're more than 3 seconds into the current chapter, go to its start
        current_chapter = self.book.chapters_metadata[self.current_chapter_index]
        if self.global_position - current_chapter.start > 3.0:
            return self.seek_to_chapter(self.current_chapter_index)
        
        # Otherwise go to the previous chapter
        prev_index = self.current_chapter_index - 1
        if prev_index < 1:
            print("Already at the first chapter")
            return False
            
        return self.seek_to_chapter(prev_index)

    def skip_forward(self, seconds: float = 30.0) -> bool:
        """Skip forward by the specified number of seconds"""
        if not self.book:
            return False
            
        new_position = min(self.global_position + seconds, self.book.duration)
        return self.seek_to_position(new_position)
    
    def skip_backward(self, seconds: float = 10.0) -> bool:
        """Skip backward by the specified number of seconds"""
        if not self.book:
            return False
            
        new_position = max(self.global_position - seconds, 0)
        return self.seek_to_position(new_position)
    
    def set_playback_speed(self, speed: float) -> bool:
        """Set the playback speed (0.5-3.0)"""
        try:
            if speed < 0.5:
                speed = 0.5
            elif speed > 3.0:
                speed = 3.0
                
            self.player.speed = speed
            return True
        except Exception as e:
            print(f"Error setting playback speed: {e}")
            return False
    
    def set_volume(self, volume: int) -> bool:
        """Set volume (0-100)"""
        try:
            if volume < 0:
                volume = 0
            elif volume > 100:
                volume = 100
            
            self.player.volume = volume
            return True
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False

    def get_current_position(self) -> float:
        """Get current global position in seconds"""
        return self.global_position
    
    def get_current_chapter(self) -> Optional[BookChapter]:
        """Get the current chapter metadata"""

        if not self.book or not self.book.chapters_metadata:
            return None
            
        if 0 <= self.current_chapter_index < len(self.book.chapters_metadata):
            return self.book.chapters_metadata[self.current_chapter_index]
        return None
    
    def get_current_file(self) -> Optional[AudioFile]:
        """Get the current audio file metadata"""
        if not self.book or not self.book.media_files:
            return None
            
        if 0 <= self.current_file_index < len(self.book.media_files):
            return self.book.media_files[self.current_file_index]
        return None
    
    def is_playing(self) -> bool:
        """Check if audio is currently playing"""
        return self.playing and not self.paused
    
    def get_progress_percentage(self) -> float:
        """Get playback progress as a percentage (0-100)"""
        if not self.book or self.book.duration <= 0:
            return 0.0
            
        return (self.global_position / self.book.duration) * 100.0
    
    def set_position_callback(self, callback: Callable[[float, int], None]) -> None:
        """Set callback for position updates (receives global position and chapter index)"""
        self.on_position_change = callback
    
    def set_chapter_callback(self, callback: Callable[[int], None]) -> None:
        """Set callback for chapter changes"""
        self.on_chapter_change = callback
    
    def set_file_callback(self, callback: Callable[[int], None]) -> None:
        """Set callback for file changes"""
        self.on_file_change = callback
    
    def set_playback_end_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for end of playback"""
        self.on_playback_end = callback
    
    def set_download_progress_callback(self, callback: Callable[[int, float], None]) -> None:
        """Set callback for download progress updates"""
        self.on_download_progress = callback


    # Internal Methods

    def _track_position(self) -> None:
        """Thread to track playback position."""
        last_chapter = self.current_chapter_index
        last_check_time = time.time()

        while self.playing and not self._stop_requested:
            if not self.paused and self.book:
                try:
                    local_pos = self.player.time_pos
                    if local_pos is not None:
                        self.track_position = local_pos

                        file_offset = self._get_file_offset(self.current_file_index)
                        self.global_position = file_offset + local_pos

                        # Check for chapter change
                        chapter_idx = self._get_chapter_from_position(self.global_position)
                        if chapter_idx != last_chapter:
                            self.current_chapter_index = chapter_idx
                            last_chapter = chapter_idx
                            if self.on_chapter_change:
                                self.on_chapter_change(chapter_idx)

                        if self.on_position_change:
                            self.on_position_change(self.global_position, self.current_chapter_index)

                        # Check if we're near the end of the current file
                        current_file = self.book.media_files[self.current_file_index]
                        if local_pos > current_file.duration - 0.5:
                            # Check if the time has been stuck here for more than 2 seconds
                            current_time = time.time()
                            if current_time - last_check_time > 2.0:
                                print("Detected playback stuck near file end - forcing transition")
                                self._handle_track_end()
                        last_check_time = time.time()
                    else:
                        # if time_pos is None, but we're supposed to be playing
                        # Might have missed the EOF event
                        if time.time() - last_check_time > 2.0:
                            print("No position reported for 2 seconds - checking if we need to transition.")
                            if self.current_file_index < len(self.book.media_files) - 1:
                                self._handle_track_end()
                        last_check_time = time.time()

                except Exception as e:
                    print(f"Error tracking position: {e}")

            time.sleep(0.2)

    def _handle_track_end(self) -> None:
        """Handle end of current track"""
        if not self.book or self._stop_requested:
            return

        if self._handling_track_end.is_set():
            print("Already handling track end, ignoring duplicate event")
            return
        try:
            self._handling_track_end.set()
            with threading.Lock():
                next_file_index = self.current_file_index + 1
                if next_file_index < len(self.book.media_files):
                    print(f"Track ended, moving to next file (index: {next_file_index})")
                    
                    file_path = None
                    if self.current_book_id in self.downloaded_files:
                        file_path = self.downloaded_files[self.current_book_id].get(next_file_index)
                
                    if not file_path:
                        print("Next file not yet downloaded, loading...")
                        success = self._download_file(next_file_index, wait=True)
                        if not success:
                            print("Failed to download next file, stopping playback.")
                            self._handle_playback_end()
                            return
                        file_path = self.downloaded_files[self.current_book_id].get(next_file_index)

                    self.current_file_index = next_file_index
                    self.track_position = 0.0

                    file_offset = self._get_file_offset(self.current_file_index)
                    self.global_position = file_offset                

                    def play_next_file():
                        try:
                            print(f"Playing next file: {file_path}")
                            self.player.play(file_path)

                            time.sleep(1.0)

                            if os.path.basename(self.player.path) != os.path.basename(file_path):
                                print("Warning: Next file did not load properly")
                                self.player.play(file_path)

                            print(f"Successfully started playing next file {next_file_index}")
                        except Exception as e:
                            print(f"Error starting next file: {e}")
                            self._handle_playback_end()

                    threading.Thread(target=play_next_file, daemon=True).start()
                    self._download_file(next_file_index + 1, wait=False)

                    if self.on_file_change:
                        self.on_file_change(next_file_index)
                else:
                    # End of book
                    self._handle_playback_end()
        finally:
            self._handling_track_end.clear()

    def _handle_playback_end(self) -> None:
        """Handle end of book playback"""
        print("End of book reached")
        self.playing = False
        self.paused = False

        if self.on_playback_end:
            self.on_playback_end()

    def _get_file_from_position(self, position: float) -> Tuple[int, float]:
        """Convert a global position to a file index and local position"""
        if not self.book or not self.book.media_files:
            return 0, 0.0

        current_offset = 0.0
        for i, file in enumerate(self.book.media_files):
            file_end = current_offset + file.duration
            if position < file_end or i == len(self.book.media_files) - 1:
                # This is the file we want
                local_position = position - current_offset
                return i, local_position
            current_offset = file_end

        return len(self.book.media_files) - 1, 0.0

    def _get_file_offset(self, file_index: int) -> float:
        """Get the global position offset for the start of a file."""
        if not self.book or not self.book.media_files:
            return 0.0

        offset = 0.0
        for i in range(file_index):
            if i < len(self.book.media_files):
                offset += self.book.media_files[i].duration

        return offset

    def _get_chapter_from_position(self, position: float) -> int:
        """Find the current chapter index for a given global position"""
        if not self.book or not self.book.chapters_metadata:
            return 0

        #print(self.book.chapters_metadata)
        for i, chapter in enumerate(self.book.chapters_metadata):
            if chapter.start <= position < chapter.end or i == len(self.book.chapters_metadata):
                return i

        return 0

    def _start_download_worker(self):
        """Start a background thread to process download queue."""
        def worker():
            while True:
                try:
                    # Get next download task
                    task = self.download_queue.get()
                    if task is None:
                        break

                    book_id, file_index, callback = task
                    self._process_download(book_id, file_index, callback)

                    # Mark as done
                    self.download_queue.task_done()
                except Exception as e:
                    print(f"Error in download worker: {e}")

        self.download_thread = threading.Thread(target=worker, daemon=True)
        self.download_thread.start()

    def _match_cache_key(self, book_id, file_index: int) -> bool:
        current_key = self.downloaded_files[book_id][file_index]
        current_book_key = self.api._get_file_cache_key(self.book.title, file_index)
        if current_key == current_book_key:
            return True
        else:
            return False

    def _process_download(self, book_id, file_index, completion_callback):
        """Process a single download task."""
        with self.download_lock:
            self.is_downloading = True

        success = False
        try:
            if not self.book or not self.book.media_files:
                return False
            if file_index < 0 or file_index >= len(self.book.media_files):
                return False

            # Already downloaded in this session?
            if book_id in self.downloaded_files and file_index in self.downloaded_files[book_id]:
                print("ALRADY DOWNLALDED")
                success = True
                if completion_callback:
                    completion_callback(True)
                return True

            audio_file = self.book.media_files[file_index]
            cache_key = self.api._get_file_cache_key(self.book.title, file_index)

            # Check if in cache already
            cached_path = self.api._get_audio_path(cache_key)
            if cached_path:
                if book_id not in self.downloaded_files:
                    self.downloaded_files[book_id] = {}
                self.downloaded_files[book_id][file_index] = str(cached_path)
                success = True
                if completion_callback:
                    completion_callback(True)
                return True

            print(f"Downloading file {file_index}")

            def progress_update(downloaded, total):
                if self.on_download_progress and total > 0:
                    progress = (downloaded / total)*100
                    self.on_download_progress(file_index, progress)

            file_path = self.api.download_audio(
                cache_key,
                audio_file.url,
                progress_callback=progress_update
            )

            if file_path:
                if book_id not in self.downloaded_files:
                    self.downloaded_files[book_id] = {}
                self.downloaded_files[book_id][file_index] = str(file_path)
                print(f"Downloaded and cached file {file_index} for book {book_id}")
                success = True
            else:
                print(f"Failed to download file {file_index} for book {book_id}")
                success = False

        except Exception as e:
            print(f"Error downloading file {file_index} for book {book_id}: {e}")
            success = False

        finally:
            with self.download_lock:
                self.is_downloading = False

            if completion_callback:
                completion_callback(success)

            return success
        

    def _download_file(self, file_index: int, wait=False) -> bool:
        """Queue a file for download, optionally waiting for completion."""
        if not self.book or not self.book.media_files:
            return False

        if file_index < 0 or file_index >= len(self.book.media_files):
            return False

        # Check if already downloaded
        if self.current_book_id in self.downloaded_files and file_index in self.downloaded_files[self.current_book_id]:
            return True

        if wait:
            result = [None]
            download_event = threading.Event()

            def completion_callback(success):
                result[0]=  success
                download_event.set()

            self.download_queue.put((self.current_book_id, file_index, completion_callback))
            download_event.wait()
            if result[0]:
                return result[0]
            else:
                return False
        else:
            self.download_queue.put((self.current_book_id, file_index, None))
            return True


    def _start_preload(self, file_index: int) -> None:
        """Start preloading the next file in the background."""
        if not self.book or file_index >= len(self.book.media_files) or file_index in self.downloaded_files:
            return

        def preload_task():
            self._download_file(file_index)

        self.preload_thread = threading.Thread(target=preload_task)
        self.preload_thread.daemon = True
        self.preload_thread.start()

    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            if self.download_queue:
                self.download_queue.put(None)
            self._stop_requested = True
            self.player.terminate()
        except:
            pass
        
            
                    
## TODO
# self.player.play() is hanging in the 'play' function. Not proceeding past that point.
