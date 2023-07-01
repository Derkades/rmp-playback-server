# Raphson music playback server

## Requirements

* Python 3
* Python dependencies, see requirements.txt
* VLC media player

## Installation

### Debian
```
apt install python3-requests python3-vlc
```

### Fedora
```
dnf install python3-requests python3-vlc
```

## Usage

1. Create a `config.json` file with credentials (see `config.json.example`).
2. Run `python3 src/server.py`

## API

See [API.md](./docs/API.md)
