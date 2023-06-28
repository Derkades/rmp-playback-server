# API

## GET `/all_playlists`

Returns a JSON array of all playlists.


## GET `/status`

Returns current playback status as json object
* `playing` bool
* `path` str (optional)

## POST `/stop`

Stop music, if currently playing.

## POST `/start`

Start music. If already playing, stop current playback and start playing a new track.
