from typing import TYPE_CHECKING, Deque, Optional
from collections import deque
from dataclasses import dataclass
from threading import Thread
import time
import traceback
import math


from requests import RequestException


if TYPE_CHECKING:
    from api import Track, Api


@dataclass
class DownloadedTrack:
    track: 'Track'
    audio: bytes


class Downloader:
    previous_playlist: Optional[str] = None
    enabled_playlists: list[str]
    cache_size: int
    cache: dict[Deque[DownloadedTrack]]
    api: 'Api'

    def __init__(self, api: 'Api', default_playlists: list[str], cache_size: int):
        self.cache = {}
        self.api = api
        self.enabled_playlists = default_playlists
        self.cache_size = cache_size

        def target():
            while True:
                try:
                    self.fill_cache()
                except:
                    traceback.print_exc()
                time.sleep(10)

        Thread(target=target, daemon=True).start()


    def fill_cache(self):
        cache_size = math.ceil(self.cache_size / len(self.enabled_playlists))
        for playlist_name in self.enabled_playlists:
            while True:
                if playlist_name in self.cache:
                    if len(self.cache[playlist_name]) >= cache_size:
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
                    print('Failed to download track for playlist', playlist_name)
                    time.sleep(1)

        print('Cache is ready')

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

    def get_track(self) -> Optional[DownloadedTrack]:
        playlist = self.select_playlist()
        if playlist is None:
            return None

        if playlist not in self.cache or len(self.cache[playlist]) == 0:
            return None

        return self.cache[playlist].popleft()
