import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from player import AudioPlayer
from api import Api
from downloader import Downloader


class App:
    api: Api
    player: AudioPlayer
    downloader: Downloader

    def __init__(self):
        with open('config.json', 'r') as config_file:
            config = json.load(config_file)

        self.api = Api(config)
        self.downloader = Downloader(self.api, config['default_playlists'], config["cache_size"])
        self.player = AudioPlayer(config["use_shm"], self.api, self.downloader)

        self.start_server(config['bind'], config['port'])

    def start_server(app, bind: str, port: int):
        class RequestHandler(BaseHTTPRequestHandler):

            def respond(self, content_type: str, response: bytes):
                self.send_response(200)
                self.send_header('Content-Type', content_type)
                self.end_headers()
                self.wfile.write(response)

            def respond_ok(self) -> None:
                self.respond('text/plain', b'ok')

            def respond_json(self, obj) -> None:
                self.respond('application/json', json.dumps(obj).encode())

            def post_body(self) -> str:
                content_length = int(self.headers.get('Content-Length'))
                return self.rfile.read(content_length).decode()

            def do_GET(self):
                if self.path == '/':
                    with Path(Path(__file__).parent, 'index.html').open('rb') as index_file:
                        self.respond('text/html', index_file.read())
                    return

                if self.path == '/state':
                    data = {
                        'playlists': {
                            'all': list(app.api.playlists.keys()),
                            'enabled': app.downloader.enabled_playlists,
                        },
                        'player': {
                            'has_media': app.player.has_media(),
                            'is_playing': app.player.is_playing(),
                            'position': app.player.postition(),
                            'position_percent': app.player.postition_percent(),
                            'duration': app.player.duration(),
                            'volume': app.player.volume(),
                        }
                    }
                    if app.player.currently_playing:
                        track = app.player.currently_playing.track
                        data['currently_playing'] = {
                            'path': track.path,
                            'duration': track.duration,
                            'title': track.title,
                            'album': track.album,
                            'album_artist': track.album_artist,
                            'year': track.year,
                            'artists': track.artists,
                        }
                    else:
                        data['currently_playing'] = None

                    self.respond_json(data)
                    return

                if self.path == '/image':
                    if app.player.currently_playing:
                        self.respond('image/webp', app.player.currently_playing.image)
                    else:
                        self.send_response(400) # Bad Request
                        self.end_headers()
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
                    position = int(self.post_body())
                    app.player.seek(position)
                    self.respond_ok()
                    return

                if self.path == '/volume':
                    volume = int(self.post_body())
                    app.player.set_volume(volume)
                    self.respond_ok()
                    return

                if self.path == '/playlists':
                    playlists = json.loads(self.post_body())
                    assert isinstance(playlists, list)
                    for playlist in playlists:
                        assert isinstance(playlist, str)
                        assert playlist in app.api.playlists
                    print('Changed enabled playlists:', playlists)
                    app.downloader.enabled_playlists = playlists
                    self.respond_ok()
                    return

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
