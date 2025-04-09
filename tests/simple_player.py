import time
import os
import sys
from app2.Player import MPVPlayer

def print_time(position):
    minutes, seconds = divmod(int(position), 60)
    print(f"Position: {minutes:02d}:{seconds:02d}", end="\r")

def playback_ended():
    print("\nPlayback ended")

def main():
    # Check if file path is provided
    if len(sys.argv) < 2:
        print("Usage: python test_mpv_player.py <path_to_mp3>")
        return
        
    file_path = sys.argv[1]
    if not os.path.exists(file_path):
        print(f"Error: File not found: {file_path}")
        return
        
    # Create player
    player = MPVPlayer()
    
    # Set callbacks
    player.set_position_callback(print_time)
    player.set_playback_end_callback(playback_ended)
    
    # Load file
    if not player.load_file(file_path):
        print("Failed to load file")
        return
        
    # Start playback
    player.play()
    
    try:
        while True:
            cmd = input("\nEnter command (play/pause/stop/seek/volume/info/quit): ").strip().lower()
            
            if cmd == "play":
                player.play()
            elif cmd == "pause":
                player.pause()
            elif cmd == "stop":
                player.stop()
            elif cmd == "seek":
                pos = float(input("Enter position in seconds: "))
                player.set_position(pos)
            elif cmd == "volume":
                vol = int(input("Enter volume (0-100): "))
                player.set_volume(vol)
            elif cmd == "info":
                pos = player.get_position()
                dur = player.get_duration()
                print(f"Position: {pos:.2f}s / {dur:.2f}s ({(pos/dur*100):.1f}%)")
                print(f"Status: {'Playing' if player.is_playing() else 'Paused' if player.paused else 'Stopped'}")
            elif cmd == "quit":
                player.stop()
                break
    except KeyboardInterrupt:
        player.stop()
        print("\nExiting...")

if __name__ == "__main__":
    main()
