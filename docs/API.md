# API

## GET `/state`

```json
{
  "playlists": {
    "all": ["CB", "DK", "JK", "JM", "MA"], // List of all playlist names
    "enabled": ["CB", "JK"] // List of enabled playlist names
  },
  "player": {
    "has_media": true, // True when paused or playing, false when stopped.
    "is_playing": true, // True when playing, false when paused or stopped
    "position": 15, // Current playback position (-1 when stopped)
    "position_percent": 7, // Current playback position, as a percentage
    "duration": 207, // Total track duration as reported by VLC (-1 when stopped)
    "volume": 100 // VLC volume (0-100, -1 when stopped, 0 at initial startup)
  },
  "currently_playing": { // May be null. Present if has_media is true
    "path": "JK/25. Resist and Bite.mp3",
    "duration": 207, // Duration as reported by the server. For seek bars, use the duration in the player section instead.
    "title": "Resist And Bite", // May be null
    "album": "War And Victory - Best Of...Sabaton", // May be null
    "album_artist": "Sabaton", // May be null
    "year": 2016, // May be null
    "artists": [ // May be null
      "Sabaton"
    ],
    "tags": [ // May be empty, but never null
      "Power Metal"
    ]
  }
}
```

## GET `/image`

Album cover image for currently playing track. Responds with status code 400 if no track is playing.

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

### POST `/volume`

Set player volume. Post body should be set to an integer 0-100.
