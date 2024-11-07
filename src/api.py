from typing import Any, cast
import uuid
from dataclasses import dataclass
from urllib.parse import quote
import requests


@dataclass
class Track:
    path: str
    duration: int
    title: str
    album: str
    album_artist: str
    year: int
    artists: list[str] | None


@dataclass
class DownloadedTrack:
    track: Track
    audio: bytes


@dataclass
class Playlist:
    name: str


class Api():
    server: str
    headers: dict[str, str]
    playlists: dict[str, Playlist] = {}
    player_id: str
    csrf: str | None = None

    def __init__(self, config):
        self.server = config['server']
        self.player_id = str(uuid.uuid4())
        self.headers = {'User-Agent': 'rmp-playback-server'}
        print('Logging in')
        token = self._post('/auth/login', {'username': config['username'], 'password': config['password']}).json()['token']
        self.headers['Cookie'] = 'token=' + token

        print("Getting CSRF token")
        self.csrf = cast(str, self._get('/auth/get_csrf').json()['token'])

        self.update_playlists()

    def _get(self, endpoint: str):
        r = requests.get(self.server + endpoint, headers=self.headers, timeout=60)
        r.raise_for_status()
        return r

    def _post(self, endpoint: str, json: Any):
        if self.csrf:
            json['csrf'] = self.csrf
        r = requests.post(self.server + endpoint,
                          headers={'Content-Type': 'application/json', **self.headers},
                          json=json,
                          timeout=60)
        r.raise_for_status()
        return r

    def update_playlists(self):
        print('Updating playlists')

        self.playlists = {}
        for playlist in self._get('/playlist/list').json():
            self.playlists[playlist['name']] = Playlist(playlist['name'])

    def choose_track(self, playlist: str) -> Track:
        json = self._post('/playlist/' + quote(playlist) + '/choose_track', {}).json()
        return Track(json['path'], json['duration'], json['title'], json['album'], json['album_artist'], json['year'], json['artists'])

    def get_audio(self, track_path: str) -> bytes:
        return self._get('/track/' + track_path + '/audio?type=webm_opus_high').content

    def get_cover_image(self, track_path: str) -> bytes:
        return self._get('/track/' + track_path + '/cover?quality=high').content

    def submit_now_playing(self, track_path: str, progress: int, paused: bool) -> None:
        print('Submit now playing')
        self._post('/activity/now_playing',
                   {'player_id': self.player_id,
                    'track': track_path,
                    'paused': paused,
                    'progress': progress})

    def submit_played(self, track_path: str, timestamp: int):
        print('Submit played')
        self._post('/activity/played', {'track': track_path, 'timestamp': timestamp})
