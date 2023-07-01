import json
from http.server import BaseHTTPRequestHandler, HTTPServer

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
        self.downloader = Downloader(self.api)
        self.player = AudioPlayer(self.api, self.downloader, config['default_playlists'])

        self.downloader.fill_cache(self.player.enabled_playlists)

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
                    app.downloader.fill_cache(playlists)

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
