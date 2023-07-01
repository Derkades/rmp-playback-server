# API

## GET `/status`

To be documented, endpoint is still frequently changing.

## POST `/playlists`

Set enabled playlists. Post body should be a json array of playlist names.

## POST `/stop`

Stop music, if currently playing. Nothing happens if no music is playing.

## POST `/pause`

Pauses music. Nothing happens if music is already paused or no music is playing.

## POST `/play`

If music is paused, playback is resumed. If no music was playing, a new track is loaded and started. If no playlists are enabled, nothing happens.

## POST `/next`

A new track is loaded from the next playlist, and started. If no playlists are enabled, nothing happens.
