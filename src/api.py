import uuid
import time
from dataclasses import dataclass

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
    tracks: dict[str, Track]


class Api():
    server: str
    headers: dict[str, str]
    playlists: dict[str, Playlist]
    tracks: dict[str, Track]
    player_id: str
    cached_csrf: str = None
    cached_csrf_time: int = 0

    def __init__(self, config):
        self.server = config['server']
        self.player_id = str(uuid.uuid4())
        self.headers = {'User-Agent': 'rmp-playback-server'}
        print('Logging in')
        r = requests.post(self.server + '/auth/login',
                        headers={'Content-Type': 'application/json', **self.headers},
                        json={'username': config['username'], 'password': config['password']})
        r.raise_for_status()
        token = r.json()['token']
        self.headers['Cookie'] = 'token=' + token

        self.update_track_list()

    def update_track_list(self):
        print('Downloading playlist and track list')
        r = requests.get(self.server + '/track/list',
                         headers=self.headers)
        r.raise_for_status()

        track_list = r.json()
        self.playlists = {}
        self.tracks = {}

        for playlist in track_list['playlists']:
            tracks: dict[str, Track] = {}
            for track in playlist['tracks']:
                track_obj = Track(track['path'],
                                  track['duration'],
                                  track['title'],
                                  track['album'],
                                  track['album_artist'],
                                  track['year'],
                                  track['artists'])
                tracks[track['path']] = track_obj
                self.tracks[track['path']] = track_obj

            self.playlists[playlist['name']] = Playlist(playlist['name'], tracks)

    def csrf(self) -> str:
        if time.time() - self.cached_csrf_time > 30*60:
            print("Getting new CSRF token")
            r = requests.get(self.server + '/auth/get_csrf', headers=self.headers)
            r.raise_for_status()
            self.cached_csrf = r.json()['token']
            self.cached_csrf_time = int(time.time())

        return self.cached_csrf

    def choose_track(self, playlist: str) -> str:
        csrf = self.csrf()
        r = requests.post(self.server + '/track/choose',
                          headers={'Content-Type': 'application/json', **self.headers},
                          json={'csrf': csrf,
                                'playlist_dir': playlist})
        r.raise_for_status()
        return r.json()['path']

    def download_to_pipe(self, track_path: str, stdin) -> None:
        r = requests.get(self.server + '/track/audio',
                         params={'path': track_path,
                                 'type': 'webm_opus_high'},
                         headers=self.headers,
                         stream=True)
        r.raise_for_status()
        for chunk in r.iter_content(4096):
            stdin.write(chunk)

    def get_audio(self, track_path: str) -> bytes:
        r = requests.get(self.server + '/track/audio',
                         params={'path': track_path,
                                 'type': 'webm_opus_high'},
                         headers=self.headers)
        r.raise_for_status()
        return r.content

    def get_cover_image(self, track_path: str) -> bytes:
        r = requests.get(self.server + '/track/album_cover',
                         params={'path': track_path,
                                 'quality': 'high'},
                         headers=self.headers)
        r.raise_for_status()
        return r.content

    def submit_now_playing(self, track_path: str, progress: int, paused: bool) -> None:
        print('Submit now playing')
        csrf = self.csrf()
        r = requests.post(self.server + '/activity/now_playing',
                          json={'csrf': csrf,
                                'player_id': self.player_id,
                                'track': track_path,
                                'paused': paused,
                                'progress': progress},
                          headers={'Content-Type': 'application/json',
                                   **self.headers})
        r.raise_for_status()


    def submit_played(self, track_path: str):
        print('Submit played')
        csrf = self.csrf()
        r = requests.post(self.server + '/activity/played',
                          json={'csrf': csrf,
                                'track': track_path,
                                'lastfmEligible': False},  # TODO determine eligibility properly
                          headers={'Content-Type': 'application/json',
                                   **self.headers})
        r.raise_for_status()
