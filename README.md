> [!WARNING]
> This project has been largely abandoned. While the application is functional, after spending several hours on it, I realized that I had essentially recreated the existing web player with more bugs and slightly worse performance.


# ABS-Client

ABS-Client is a desktop client for an Audiobookshelf server. It allows users to browse their audiobook library, play books, and navigate chapters. The client includes basic media controls powered by MPV for a seamless listening experience.

## Features

- Browse your Audiobookshelf library.
- Play audiobooks directly from the desktop client.
- Chapter navigation for easier access to specific sections.
- Basic media controls (play, pause, stop, etc.) using MPV.

## Requirements

- Python3.12
- Audiobookshelf server (compatible version)
- MPV player

## Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/CSJ7701/ABS-Client.git
   ```
2. Install the required dependencies:
   ```bash
   poetry install
   ```
   If you do not use poetry, you can open the `pyproject.toml` file to see the list of dependencies.
   
4. Run the client:
   ```bash
   python -m app.App
   ```

## TODO

- [ ] Fix crashes related to `QPainter` errors.
- [ ] Resolve hangs caused by repeated pausing during playback.

---
