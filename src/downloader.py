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
    image: bytes


class Downloader:
    previous_playlist: Optional[str] = None
    enabled_playlists: list[str]
    cache_size: int
    cache: dict[str, Deque[DownloadedTrack]]
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
                time.sleep(1)

        Thread(target=target, daemon=True).start()


    def fill_cache(self):
        """
        Ensure cache contains enough downloaded tracks
        """
        if len(self.enabled_playlists) == 0:
            return

        for playlist_name in self.enabled_playlists:
            if playlist_name in self.cache:
                if len(self.cache[playlist_name]) >= self.cache_size:
                    break
            else:
                self.cache[playlist_name] = deque()

            try:
                track = self.api.choose_track(playlist_name)
                print('Download:', track.path)

                audio = self.api.get_audio(track.path)
                image = self.api.get_cover_image(track.path)
                downloaded = DownloadedTrack(track, audio, image)
                self.cache[playlist_name].append(downloaded)
            except RequestException:
                print('Failed to download track for playlist', playlist_name)
                traceback.print_exc()
                time.sleep(1)

    def select_playlist(self) -> Optional[str]:
        """
        Choose a playlist to play a track from.
        """
        if len(self.enabled_playlists) == 0:
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
        """
        Get the next track to play
        """
        playlist = self.select_playlist()
        if playlist is None:
            return None

        if playlist not in self.cache or len(self.cache[playlist]) == 0:
            return None

        return self.cache[playlist].popleft()
