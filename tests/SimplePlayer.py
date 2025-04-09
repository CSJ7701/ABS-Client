import mpv
import time
import threading
import os
from typing import Optional, Callable

class MPVPlayer:
    def __init__(self):
        # Basic MPV setup
        self.player = mpv.MPV(video=False, terminal=False, quiet=False)
        
        # State tracking
        self.playing = False
        self.paused = False
        self.position = 0.0
        self.duration = 0.0
        self._stop_requested = False
        
        # Thread for position tracking
        self.position_thread = None
        
        # Callbacks
        self.on_position_change = None
        self.on_playback_end = None
        
        # Register end file event
        @self.player.property_observer("eof-reached")
        def handle_end(_name, value):
            if value and self.playing:
                self._handle_end_reached()
        
        # Set default volume
        self.set_volume(100)
    
    def load_file(self, file_path: str) -> bool:
        """Load a media file for playback"""
        if not os.path.exists(file_path):
            print(f"Error: File not found: {file_path}")
            return False
        
        try:
            # Reset state
            self.playing = False
            self.paused = False
            
            # Load the file
            self.player.play(file_path)
            
            # Wait for file to load
            retry = 0
            while retry < 10:
                try:
                    self.duration = self.player.duration or 0
                    if self.duration > 0:
                        break
                except:
                    pass
                time.sleep(0.1)
                retry += 1
            
            print(f"Loaded file: {file_path} (Duration: {self.duration:.2f}s)")
            return True
        except Exception as e:
            print(f"Error loading file: {e}")
            return False
    
    def play(self) -> bool:
        """Start or resume playback"""
        try:
            if self.paused:
                # If paused, resume playback
                self.player.pause = False
                self.paused = False
                self.playing = True
                print("Resumed playback")
            else:
                # Start new playback
                self.player.pause = False
                self._stop_requested = False
                self.playing = True
                self.paused = False
                
                # Start position tracking thread if not already running
                if not self.position_thread or not self.position_thread.is_alive():
                    self.position_thread = threading.Thread(target=self._track_position)
                    self.position_thread.daemon = True
                    self.position_thread.start()
                
                print("Started playback")
            
            return True
        except Exception as e:
            print(f"Error playing: {e}")
            return False
    
    def pause(self) -> bool:
        """Pause playback"""
        try:
            if self.playing and not self.paused:
                self.player.pause = True
                self.paused = True
                print("Paused playback")
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
            print("Stopped playback")
            return True
        except Exception as e:
            print(f"Error stopping: {e}")
            return False
    
    def set_position(self, position_seconds: float) -> bool:
        """Seek to a specific position in seconds"""
        try:
            if position_seconds < 0 or (self.duration > 0 and position_seconds > self.duration):
                print(f"Invalid position: {position_seconds} (duration: {self.duration})")
                return False
            
            self.player.seek(position_seconds, reference="absolute")
            print(f"Seeked to position: {position_seconds:.2f}s")
            return True
        except Exception as e:
            print(f"Error seeking: {e}")
            return False
    
    def set_volume(self, volume: int) -> bool:
        """Set volume (0-100)"""
        try:
            if volume < 0:
                volume = 0
            elif volume > 100:
                volume = 100
            
            # MPV volume is 0-100
            self.player.volume = volume
            print(f"Set volume to {volume}")
            return True
        except Exception as e:
            print(f"Error setting volume: {e}")
            return False
    
    def get_position(self) -> float:
        """Get current playback position in seconds"""
        try:
            if not self.playing:
                return 0.0
            
            pos = self.player.time_pos
            return pos if pos is not None else 0.0
        except:
            return 0.0
    
    def get_duration(self) -> float:
        """Get media duration in seconds"""
        try:
            return self.player.duration or self.duration
        except:
            return self.duration
    
    def is_playing(self) -> bool:
        """Check if media is currently playing"""
        return self.playing and not self.paused
    
    def set_position_callback(self, callback: Callable[[float], None]) -> None:
        """Set callback for position updates"""
        self.on_position_change = callback
    
    def set_playback_end_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for end of playback"""
        self.on_playback_end = callback
    
    def _track_position(self) -> None:
        """Thread to track playback position"""
        while self.playing and not self._stop_requested:
            if not self.paused:
                try:
                    pos = self.get_position()
                    self.position = pos
                    
                    if self.on_position_change:
                        self.on_position_change(pos)
                except:
                    pass
            
            time.sleep(0.2)  # Update 5 times per second
    
    def _handle_end_reached(self) -> None:
        """Handle end of media event"""
        print("End of media reached")
        self.playing = False
        self.paused = False
        
        if self.on_playback_end:
            self.on_playback_end()
    
    def __del__(self):
        """Clean up resources when the object is destroyed"""
        try:
            self._stop_requested = True
            self.player.terminate()
        except:
            pass
