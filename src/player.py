from tempfile import _TemporaryFileWrapper, NamedTemporaryFile
from threading import Thread
from typing import TYPE_CHECKING, Optional
import time

import vlc
from requests import RequestException

if TYPE_CHECKING:
    from downloader import DownloadedTrack
    from server import Api
    from downloader import Downloader


class AudioPlayer():
    temp_file: '_TemporaryFileWrapper[bytes] | None' = None
    downloader: 'Downloader'
    api: 'Api'
    currently_playing: Optional['DownloadedTrack'] = None
    vlc_instance: vlc.Instance
    vlc_player: vlc.MediaPlayer
    vlc_events: vlc.EventManager
    start_timestamp: int = 0

    def __init__(self,
                 api: 'Api',
                 downloader: 'Downloader'):
        self.api = api
        self.downloader = downloader

        self.vlc_instance = vlc.Instance('--file-caching=0')
        self.vlc_player = self.vlc_instance.media_player_new()
        self.vlc_events = self.vlc_player.event_manager()
        self.vlc_events.event_attach(vlc.EventType.MediaPlayerEndReached, self.on_media_end)

        self._now_playing_submitter()

    def on_media_end(self, event):
        print('Media ended, play next')
        def target():
            if self.currently_playing:
                # save current info before it is replaced by the next track
                path = self.currently_playing.track.path
                start_timestamp = self.start_timestamp
                def submit_played():
                    self.api.submit_played(path, start_timestamp)
                # submit in other thread, so next track can start immediately
                Thread(target=submit_played).start()

            self.next(retry=True)

        Thread(target=target).start()

    def stop(self):
        try:
            self.vlc_player.stop()
            self.vlc_player.set_media(None)
            self.currently_playing = None
        finally:
            if self.temp_file:
                self.temp_file.close()

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
            return

        self.currently_playing = download
        self.start_timestamp = int(time.time())
        print('Playing track:', download.track.path)

        temp_file = NamedTemporaryFile('wb', prefix='rmp-playback-server-')

        try:
            temp_file.truncate(0)
            temp_file.write(download.audio)

            media = self.vlc_instance.media_new(temp_file.name)
            self.vlc_player.set_media(media)
            self.vlc_player.play()
        finally:
            # Remove old temp file
            if self.temp_file:
                self.temp_file.close()
            # Store current temp file so it can be removed later
            self.temp_file = temp_file

    def has_media(self) -> bool:
        return self.vlc_player.get_media() is not None

    def is_playing(self) -> bool:
        return self.vlc_player.is_playing() == 1

    def position(self) -> int:
        return self.vlc_player.get_time() // 1000

    def duration(self) -> int:
        return self.vlc_player.get_length() // 1000

    def position_percent(self) -> int:
        if self.vlc_player.get_length() == 0:
            return 0
        return int(self.vlc_player.get_time() / self.vlc_player.get_length() * 100)

    def seek(self, position: int):
        print('Seek to:', position)
        self.vlc_player.set_time(position * 1000)

    def volume(self) -> int:
        return self.vlc_player.audio_get_volume()

    def set_volume(self, volume: int):
        return self.vlc_player.audio_set_volume(volume)

    def _now_playing_submitter(self):
        def target():
            while True:
                try:
                    if self.has_media() and self.currently_playing:
                        self.api.submit_now_playing(self.currently_playing.track.path,
                                                    self.postition_percent(),
                                                    not self.is_playing())
                except RequestException:
                    print('Failed to submit now playing info')

                time.sleep(10)

        Thread(target=target, daemon=True).start()
