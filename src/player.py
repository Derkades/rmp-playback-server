from threading import Thread
from typing import TYPE_CHECKING, Optional
import tempfile
import os
import time
import traceback

import vlc
from requests import RequestException

if TYPE_CHECKING:
    from api import Track
    from server import Api
    from downloader import Downloader


class AudioPlayer():
    temp_file: str
    downloader: 'Downloader'
    api: 'Api'
    currently_playing: Optional['Track'] = None
    vlc_instance: vlc.Instance
    vlc_player: vlc.MediaPlayer
    vlc_events: vlc.EventManager

    def __init__(self,
                 use_shm: bool,
                 api: 'Api',
                 downloader: 'Downloader'):
        self.temp_file = '/dev/shm/rmp-audio' if use_shm else '/tmp/rmp-audio'
        self.api = api
        self.downloader = downloader

        self.vlc_instance = vlc.Instance('--file-caching=0')
        self.vlc_player = self.vlc_instance.media_player_new()
        self.vlc_events = self.vlc_player.event_manager()
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)

        self.now_playing_submitter()

    def on_media_end(self, event):
        print('Media ended, play next')
        def target():
            self.api.submit_played(self.currently_playing.path)
            self.next(retry=True)
        Thread(target=target, daemon=True).start()

    def stop(self):
        self.vlc_player.stop()
        self.vlc_player.set_media(None)
        self.currently_playing = None

    def pause(self):
        self.vlc_player.set_pause(True)

    def play(self):
        if self.has_media():
            self.vlc_player.play()
        else:
            self.next()

    def next(self, retry=False):
        download = self.downloader.get_track()
        if not download:
            print('No cached track available')
            if retry:
                print('Retry enabled, going to try again')
                time.sleep(5)
                self.next(retry)

        self.currently_playing = download.track
        print('Playing track:', download.track.path)

        with open(self.temp_file, 'wb') as audio_file:
            audio_file.write(download.audio)

        media = self.vlc_instance.media_new(self.temp_file)
        self.vlc_player.set_media(media)
        self.vlc_player.play()

    def has_media(self) -> bool:
        return self.vlc_player.get_media() is not None

    def is_playing(self) -> bool:
        return self.vlc_player.is_playing() == 1

    def postition(self) -> int:
        return self.vlc_player.get_time() // 1000

    def duration(self) -> int:
        return self.vlc_player.get_length() // 1000

    def postition_percent(self) -> int:
        return int(self.vlc_player.get_time() / self.vlc_player.get_length() * 100)

    def seek(self, position: int):
        print('Seek to:', position)
        self.vlc_player.set_time(position * 1000)

    def now_playing_submitter(self):
        def target():
            while True:
                try:
                    if self.has_media() and self.currently_playing:
                        self.api.submit_now_playing(self.currently_playing.path,
                                                    self.postition_percent(),
                                                    not self.is_playing())
                except RequestException:
                    print('Failed to submit now playing info')

                time.sleep(10)

        Thread(target=target, daemon=True).start()
