from typing import TYPE_CHECKING, Deque
from collections import deque
from dataclasses import dataclass
from threading import Thread
import time


from requests import RequestException


if TYPE_CHECKING:
    from api import Track, Api


@dataclass
class DownloadedTrack:
    track: 'Track'
    audio: bytes


class Downloader:
    cache_size = 2
    cache: dict[Deque[DownloadedTrack]]
    api: 'Api'

    def __init__(self, api):
        self.cache = {}
        self.api = api

    def fill_cache(self, enabled_playlists: list[str]):
        Thread(target=lambda: self._fill_cache(enabled_playlists), daemon=True).start()

    def _fill_cache(self, enabled_playlists: list[str]):
        for playlist_name in enabled_playlists:
            while True:
                if playlist_name in self.cache:
                    if len(self.cache[playlist_name]) >= self.cache_size:
                        break
                else:
                    self.cache[playlist_name] = deque()

                try:
                    track_path = self.api.choose_track(playlist_name)
                    print('Download:', track_path)

                    if track_path not in self.api.tracks:
                        print('Track not in local track list')
                        time.sleep(1)
                        continue

                    track = self.api.tracks[track_path]
                    audio = self.api.get_audio(track_path)
                    downloaded = DownloadedTrack(track, audio)
                    self.cache[playlist_name].append(downloaded)
                except RequestException:
                    print('Failed to download track')
                    time.sleep(1)

        print('Cache is ready')

    def get_track(self, playlist: str) -> DownloadedTrack:
        if playlist not in self.cache or len(self.cache[playlist]) == 0:
            print('Cache is empty for this playlist. Trying again...')
            time.sleep(1)
            return self.get_track(playlist)

        return self.cache[playlist].popleft()
