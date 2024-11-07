# Raphson music playback server

## Installation

### Dependencies
Debian:
```
apt install python3-requests python3-vlc
```
Fedora:
```
dnf install python3-requests python3-vlc
```

## Usage

1. Create a `config.json` file with credentials (see `config.json.example`).
2. Run `python3 src/server.py`

## API

See [API.md](./docs/API.md)

## Temporary files

The server writes music to temporary files so VLC can access them. On Linux, the `/tmp` directory is used for this purpose. It is strongly recommended to mount `tmpfs` on `/tmp` to avoid unnecessary writes to your disk, especially when using a Raspberry Pi with sd card.

Check if it is the case by running `mount | grep /tmp`. It should show something like: `tmpfs on /tmp type tmpfs ...`
