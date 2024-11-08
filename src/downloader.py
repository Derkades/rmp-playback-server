from datetime import date, datetime
from typing import TYPE_CHECKING
from collections import deque
from dataclasses import dataclass
from threading import Thread
import time
import traceback

from requests import RequestException

if TYPE_CHECKING:
    from api import Track, Api


@dataclass
class DownloadedTrack:
    track: 'Track | None'
    audio: bytes
    image: bytes
    lyrics: str | None


class Downloader:
    api: 'Api'
    cache: dict[str, deque[DownloadedTrack]] = {}
    previous_playlist: str | None = None
    enabled_playlists: list[str]
    cache_size: int
    news: bool
    last_news: int = 0

    def __init__(self, api: 'Api', default_playlists: list[str], cache_size: int, news: bool):
        self.api = api
        self.enabled_playlists = default_playlists
        self.cache_size = cache_size
        self.news = news

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
                    continue
            else:
                self.cache[playlist_name] = deque()

            try:
                track = self.api.choose_track(playlist_name)
                print('Download:', track.path)

                audio = self.api.get_audio(track.path)
                image = self.api.get_cover_image(track.path)
                lyrics = self.api.get_lyrics(track.path)
                downloaded = DownloadedTrack(track, audio, image, lyrics)
                self.cache[playlist_name].append(downloaded)
            except RequestException:
                print('Failed to download track for playlist', playlist_name)
                traceback.print_exc()
                time.sleep(1)

    def select_playlist(self) -> str | None:
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

    def get_track(self) -> DownloadedTrack | None:
        """
        Get the next track to play
        """
        if self.news:
            minute = datetime.now().minute
            # few minutes past the hour and last news played more than 30 minutes ago?
            if minute > 7 and minute < 15 and time.time() - self.last_news > 30*60:
                # attempt to download news
                try:
                    audio = self.api.get_news()
                    image = self.api.get_raphson()
                    self.last_news = int(time.time())
                    return DownloadedTrack(None, audio, image, None)
                except:
                    traceback.print_exc()

        playlist = self.select_playlist()
        if playlist is None:
            return None

        if playlist not in self.cache or len(self.cache[playlist]) == 0:
            return None

        return self.cache[playlist].popleft()
