import json
from dataclasses import dataclass
import subprocess
from threading import Thread
from http.server import BaseHTTPRequestHandler, HTTPServer
import uuid
import time
import traceback

import requests


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

    def __init__(self, api):
        self.api = api
        self.enabled_playlists = ['DK', 'JK']

        self.now_playing_submitter()

    def set_audio(self, audio: bytes):
        self.audio = audio

    def stop(self):
        self.process.send_signal(2)
        self.process = None
        self.currently_playing = None

    def start(self):
        if self.process:
            print('Killing existing player')
            self.process.send_signal(2)
            self.process = None

        playlist = self.select_playlist()
        track = self.api.choose_track(playlist)
        self.currently_playing = track
        print('Chosen track:', track)

        def target():
            self.process = subprocess.Popen(['ffplay', '-i', '-', '-nodisp', '-autoexit', '-hide_banner'], stdin=subprocess.PIPE)

            try:
                self.api.download_to_pipe(track, self.process.stdin)
                self.process.communicate()
            except BrokenPipeError:
                print('Broken pipe')

            self.currently_playing = None

            if self.process:
                print('Playing next track')
                self.start()

        print('Starting playback')
        Thread(target=target, daemon=True).start()

    def select_playlist(self) -> str:
        if self.previous_playlist:
            cur_index = self.enabled_playlists.index(self.previous_playlist)
            if cur_index == -1:
                self.previous_playlist = self.enabled_playlists[0]
            else:
                self.previous_playlist = self.enabled_playlists[(cur_index + 1) % len(self.enabled_playlists)]
        else:
            self.previous_playlist = self.enabled_playlists[0]

        print('Chosen playlist:', self.previous_playlist)
        return self.previous_playlist

    def now_playing_submitter(self):
        def target():
            while True:
                try:
                    if self.currently_playing:
                        self.api.submit_now_playing(self.currently_playing, 0)
                except requests.RequestException:
                    traceback.print_exc()

                time.sleep(5)

        Thread(target=target, daemon=True).start()


class Api():
    server: str
    headers: dict[str, str]
    playlists: dict[str, Playlist]
    player_id: str

    def __init__(self, config):
        self.server = config['server']
        self.player_id = str(uuid.uuid4())
        self.headers = {'User-Agent': 'rmp-playback-server'}
        r = requests.post(self.server + '/login',
                        headers={'Content-Type': 'application/json',
                                 **self.headers},
                        data=json.dumps({'username': config['username'], 'password': config['password']}))
        r.raise_for_status()
        token = r.json()['token']
        self.headers['Cookie'] = 'token=' + token

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
        # TODO cache token
        r = requests.get(self.server + '/get_csrf', headers=self.headers)
        r.raise_for_status()
        token = r.json()['token']
        return token

    def choose_track(self, playlist: str) -> str:
        csrf = self.csrf()
        r = requests.get(self.server + '/choose_track',
                         params={'csrf': csrf,
                                 'playlist_dir': playlist},
                         headers=self.headers)
        r.raise_for_status()
        return r.json()['path']

    def download_to_pipe(self, track_path: str, stdin) -> bytes:
        r = requests.get(self.server + '/get_track',
                         params={'path': track_path,
                                 'type': 'webm_opus_high'},
                         headers=self.headers,
                         stream=True)
        r.raise_for_status()
        for chunk in r.iter_content(4096):
            stdin.write(chunk)

    def submit_now_playing(self, track_path: str, progress: int):
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


class App:
    api: Api
    player: AudioPlayer

    def __init__(self):
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        self.api = Api(config)
        self.player = AudioPlayer(self.api)

        self.start_server()

    def start_server(app):
        class RequestHandler(BaseHTTPRequestHandler):

            def respond_ok(self):
                self.send_response(200)
                self.send_header('Content-Type', 'text/plain')
                self.end_headers()
                self.wfile.write(b'ok')

            def do_GET(self):
                if self.path == '/all_playlists':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps(list(app.api.playlists.keys())).encode())
                    return

                if self.path == '/status':
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    if app.player.currently_playing:
                        data = {
                            'playing': True,
                            'path': app.player.currently_playing
                        }
                    else:
                        data = {
                            'playing': False
                        }
                    self.wfile.write(json.dumps(data).encode())
                    return

                self.send_response(404)
                self.end_headers()

            def do_POST(self):
                if self.path == '/stop':
                    app.player.stop()
                    self.respond_ok()
                    return

                if self.path == '/start':
                    app.player.start()
                    self.respond_ok()
                    return

                self.send_response(404)
                self.end_headers()

        server = HTTPServer(('localhost', 8181), RequestHandler)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass

        server.server_close()


if __name__ == '__main__':
    App()
