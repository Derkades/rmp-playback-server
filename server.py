import json
from dataclasses import dataclass
import subprocess
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid
import time
import traceback
import tempfile
import os

import requests
import vlc


@dataclass
class Track:
    path: str
    duration: int
    title: str


@dataclass
class Playlist:
    name: str
    tracks: dict[str, Track]


class AudioPlayer():
    previous_playlist: str | None = None
    enabled_playlists: list[str]
    process: subprocess.Popen | None = None
    api: 'Api'
    currently_playing: str | None = None
    vlc_instance: vlc.Instance
    vlc_player: vlc.MediaPlayer
    vlc_events: vlc.EventManager

    def __init__(self, api, enabled_playlists):
        self.api = api
        self.enabled_playlists = enabled_playlists

        self.vlc_instance = vlc.Instance()
        self.vlc_player = self.vlc_instance.media_player_new()
        self.vlc_events = self.vlc_player.event_manager()
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)

        self.now_playing_submitter()

    def on_media_end(self, event):
        print('Media ended, play next')
        def target():
            self.api.submit_played(self.currently_playing)
            self.next()
        Thread(target=target, daemon=True).start()

    def stop(self):
        self.vlc_player.stop()
        self.vlc_player.set_media(None)

    def pause(self):
        self.vlc_player.set_pause(True)

    def play(self):
        if self.has_media():
            self.vlc_player.play()
        else:
            self.next()

    def next(self):
        playlist = self.select_playlist()
        if playlist is None:
            return
        track = self.api.choose_track(playlist)
        self.currently_playing = track
        print('Chosen track:', track)

        audio = self.api.get_audio(track)

        fd, name = tempfile.mkstemp()

        with os.fdopen(fd, 'wb') as audio_file:
            print('Writing audio to temp file: ', name)
            audio_file.truncate()
            audio_file.write(audio)

        media = self.vlc_instance.media_new(name)
        self.vlc_player.set_media(media)
        self.vlc_player.play()

    def has_media(self) -> bool:
        return self.vlc_player.get_media() is not None

    def is_playing(self) -> bool:
        return self.vlc_player.is_playing() == 1

    def postition(self) -> int:
        return self.vlc_player.get_time() // 1000

    def length(self) -> int:
        return self.vlc_player.get_length() // 1000

    def postition_percent(self) -> int:
        return int(self.vlc_player.get_time() / self.vlc_player.get_length() * 100)

    def seek(self, position: int):
        print('Seek to:', position)
        self.vlc_player.set_time(position * 1000)

    def select_playlist(self) -> str | None:
        if not self.enabled_playlists:
            print('No playlists enabled!')
            return None

        if self.previous_playlist:
            try:
                cur_index = self.enabled_playlists.index(self.previous_playlist)
                self.previous_playlist = self.enabled_playlists[(cur_index + 1) % len(self.enabled_playlists)]
            except ValueError:  # not in list
                self.previous_playlist = self.enabled_playlists[0]
        else:
            self.previous_playlist = self.enabled_playlists[0]

        print('Chosen playlist:', self.previous_playlist)
        return self.previous_playlist

    def now_playing_submitter(self):
        def target():
            while True:
                try:
                    if self.currently_playing:
                        self.api.submit_now_playing(self.currently_playing, self.postition_percent())
                except requests.RequestException:
                    traceback.print_exc()

                time.sleep(10)

        Thread(target=target, daemon=True).start()


class Api():
    server: str
    headers: dict[str, str]
    playlists: dict[str, Playlist]
    player_id: str
    cached_csrf: str = None
    cached_csrf_time: int = 0

    def __init__(self, config):
        self.server = config['server']
        self.player_id = str(uuid.uuid4())
        self.headers = {'User-Agent': 'rmp-playback-server'}
        print('Logging in')
        r = requests.post(self.server + '/login',
                        headers={'Content-Type': 'application/json',
                                 **self.headers},
                        data=json.dumps({'username': config['username'], 'password': config['password']}))
        r.raise_for_status()
        token = r.json()['token']
        self.headers['Cookie'] = 'token=' + token

        print('Downloading playlist and track list')
        r = requests.get(self.server + '/track_list',
                         headers=self.headers)
        r.raise_for_status()

        track_list = r.json()

        playlists: dict[str, Playlist] = {}
        for playlist in track_list['playlists']:
            tracks: dict[str, Track] = {}
            for track in playlist['tracks']:
                tracks[track['path']] = Track(track['path'], track['duration'], track['title'])

            playlists[playlist['name']] = Playlist(playlist['name'], tracks)
            self.playlists = playlists

    def csrf(self):
        if time.time() - self.cached_csrf_time < 300:
            return self.cached_csrf

        print('Getting new CSRF token')
        r = requests.get(self.server + '/get_csrf', headers=self.headers)
        r.raise_for_status()
        token = r.json()['token']
        self.cached_csrf = token
        self.cached_csrf_time = int(time.time())
        return token

    def choose_track(self, playlist: str) -> str:
        csrf = self.csrf()
        r = requests.get(self.server + '/choose_track',
                         params={'csrf': csrf,
                                 'playlist_dir': playlist},
                         headers=self.headers)
        r.raise_for_status()
        return r.json()['path']

    def download_to_pipe(self, track_path: str, stdin) -> None:
        r = requests.get(self.server + '/get_track',
                         params={'path': track_path,
                                 'type': 'webm_opus_high'},
                         headers=self.headers,
                         stream=True)
        r.raise_for_status()
        for chunk in r.iter_content(4096):
            stdin.write(chunk)

    def get_audio(self, track_path: str) -> bytes:
        r = requests.get(self.server + '/get_track',
                         params={'path': track_path,
                                 'type': 'webm_opus_high'},
                         headers=self.headers)
        r.raise_for_status()
        return r.content

    def submit_now_playing(self, track_path: str, progress: int):
        print('Submit now playing')
        csrf = self.csrf()
        r = requests.post(self.server + '/now_playing',
                          json={'csrf': csrf,
                                'player_id': self.player_id,
                                'track': track_path,
                                'paused': False,
                                'progress': progress},
                          headers={'Content-Type': 'application/json',
                                   **self.headers})
        r.raise_for_status()


    def submit_played(self, track_path: str):
        print('Submit played')
        csrf = self.csrf()
        r = requests.post(self.server + '/history_played',
                          json={'csrf': csrf,
                                'track': track_path,
                                'lastfmEligible': False},  # TODO determine eligibility properly
                          headers={'Content-Type': 'application/json',
                                   **self.headers})
        r.raise_for_status()


class App:
    api: Api
    player: AudioPlayer

    def __init__(self):
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        self.api = Api(config)
        self.player = AudioPlayer(self.api, config['default_playlists'])

        self.start_server(config['bind'], config['port'])

    def start_server(app, bind: str, port: int):
        class RequestHandler(BaseHTTPRequestHandler):

            def respond_ok(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'ok')

            def do_GET(self):
                if self.path == '/status':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    data = {
                        'all_playlists': list(app.api.playlists.keys()),
                        'enabled_playlists': app.player.enabled_playlists,
                        'has_media': app.player.has_media(),
                        'is_playing': app.player.is_playing(),
                        'current_track': app.player.currently_playing,
                        'position': app.player.postition(),
                        'position_percent': app.player.postition_percent(),
                        'length': app.player.length(),
                    }

                    self.wfile.write(json.dumps(data, indent=True).encode())
                    return

                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                if self.path == '/stop':
                    app.player.stop()
                    self.respond_ok()
                    return

                if self.path == '/pause':
                    app.player.pause()
                    self.respond_ok()
                    return

                if self.path == '/play':
                    app.player.play()
                    self.respond_ok()
                    return

                if self.path == '/next':
                    app.player.next()
                    self.respond_ok()
                    return

                if self.path == '/seek':
                    content_length = int(self.headers.get('Content-Length'))
                    input = self.rfile.read(content_length)
                    position = int(input)
                    app.player.seek(position)
                    self.respond_ok()
                    return

                if self.path == '/playlists':
                    content_length = int(self.headers.get('Content-Length'))
                    input = self.rfile.read(content_length)
                    playlists = json.loads(input.decode())
                    assert isinstance(playlists, list)
                    for playlist in playlists:
                        assert isinstance(playlist, str)
                        assert playlist in app.api.playlists
                    print('Changed enabled playlists:', playlists)
                    app.player.enabled_playlists = playlists

                self.send_response(404)
                self.end_headers()

        print(f'Starting HTTP server on {bind}:{port}')

        server = HTTPServer((bind, port), RequestHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

        server.server_close()


if __name__ == '__main__':
    App()
