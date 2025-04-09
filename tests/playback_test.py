# Initialize
from api.api import API
from app2.Player import Player
from time import sleep

# Setup API
print("Initializing API")
api = API("http://192.168.1.172:13378")
success = api.login("csj7701", "Chri$7701")
print(f"Login success: {success}")

# Setup player
print("Initializing player.")
player = Player(api)
#player.register_api(api)


# Define callbacks
def on_position_update(position: float, _):
    # Update progress UI
    if position % 5 < 0.2:
        print(f"Position: {position:.1f}s")
    
def on_playback_end():
    # Handle end of book
    print("Book completed!")
    
def on_chapter_change(chapter):
    # Update chapter display
    if chapter:
        print(f"Now playing: Chapter {chapter.id}: {chapter.title}")
    else:
        print("No chapter info...")

# Register callbacks
player.set_position_callback(on_position_update)
player.set_playback_end_callback(on_playback_end)
player.set_chapter_callback(on_chapter_change)

# Get book from API and play
print("Getting book from api...")
book_id = "b2e87d21-2907-46eb-b1e5-b619d9c34f2b"
book = api.play_item(book_id)
if not book:
    print("Failed to get book from api...")
    exit(1)
player.load_book(book)

print(f"Book: {book.title}")
print(f"Duration: {book.duration}s")
print(f"Chapters: {len(book.chapters_metadata) if book.chapters_metadata else 'None'}")
print(f"Media Files: {len(book.media_files)}")

print("Starting playback")
player.play()

# Playback controls
sleep(20)
print("Pausing")
player.pause()
sleep(10)
print("Resuming")
player.play()
sleep(10)
print("Seeking")
player.seek_to_position(300)  # Jump to 5 minutes in
sleep(10)
print("Changing volume")
player.set_volume(80)
sleep(10)
print("Stopping")
player.stop()
print("Finished")
