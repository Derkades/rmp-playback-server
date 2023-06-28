# API

## GET `/all_playlists`

Returns a JSON array of all playlist names.

## GET `/playlists`

Returns JSON array of enabled playlist names.

## GET `/status`

Returns current playback status as json object:
* `playing` bool
* `path` str (optional)

## POST `/playlists`

Set enabled playlists. Post body should be a json array of playlist names.

## POST `/stop`

Stop music, if currently playing.

## POST `/start`

Start music. If already playing, stop current playback and start playing a new track.
