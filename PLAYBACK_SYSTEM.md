# Vibey Playback System

## Overview

Vibey supports **three playback modes** to ensure users can always listen to music:

1. **Spotify Preview** (30-second clips) - Default, no login required
2. **YouTube** - Full tracks via YouTube when Spotify previews unavailable
3. **Spotify Premium** - Full tracks for logged-in Spotify Premium users

---

## How It Works

### Backend Logic

The `/v1/feed/next` endpoint returns tracks with a `playbackSource` field that tells the frontend which playback method to use:

```json
{
  "trackId": "abc123",
  "title": "Song Title",
  "artist": "Artist Name",
  "artworkUrl": "https://...",
  "audioUrl": "https://p.scdn.co/...",  // Spotify 30s preview (may be null)
  "youtubeUrl": null,  // Populated by frontend if needed
  "youtubeEmbedUrl": null,
  "spotifyUri": "spotify:track:abc123",  // For Premium users
  "playbackSource": "preview",  // "preview", "youtube", or "spotify_premium"
  "source": "spotify",
  "vibeTags": ["energetic", "upbeat"]
}
```

### Playback Source Decision Tree

```
Is user logged in with Spotify Premium?
  ├─ YES → playbackSource = "spotify_premium"
  │        Use Spotify Web Playback SDK
  │        spotifyUri = "spotify:track:xxx"
  │
  └─ NO → Does track have Spotify preview URL?
           ├─ YES → playbackSource = "preview"
           │        audioUrl = "https://p.scdn.co/..."
           │
           └─ NO → playbackSource = "youtube"
                   Frontend searches YouTube using title + artist
```

---

## Frontend Implementation

### 1. Guest Users (No Login)

**Scenario A: Track has Spotify preview**
```javascript
if (track.playbackSource === "preview" && track.audioUrl) {
  return <AudioPlayer url={track.audioUrl} />;  // HTML5 audio
}
```

**Scenario B: No Spotify preview - Use YouTube**
```javascript
if (track.playbackSource === "youtube") {
  // Search YouTube
  const youtubeVideoId = await searchYouTube(track.title, track.artist);
  
  // Option 1: Embed YouTube player
  return <YouTubePlayer videoId={youtubeVideoId} />;
  
  // Option 2: Use react-youtube or similar
  return <YouTube videoId={youtubeVideoId} opts={{...}} />;
}
```

**YouTube Search (Client-Side)**
```javascript
async function searchYouTube(title, artist) {
  const query = encodeURIComponent(`${title} ${artist} audio`);
  const response = await fetch(
    `https://www.googleapis.com/youtube/v3/search?part=snippet&q=${query}&type=video&videoCategoryId=10&maxResults=1&key=${YOUTUBE_API_KEY}`
  );
  const data = await response.json();
  return data.items[0]?.id?.videoId;
}
```

---

### 2. Spotify Premium Users

**After OAuth Login**
```javascript
// User connects Spotify
// Backend marks user_type = 'spotify'
// All subsequent feeds will have playbackSource = "spotify_premium"

if (track.playbackSource === "spotify_premium" && track.spotifyUri) {
  // Use Spotify Web Playback SDK
  spotifyPlayer.play({
    uris: [track.spotifyUri]
  });
}
```

**Setup Spotify Web Playback SDK**
```javascript
// 1. Load SDK
<script src="https://sdk.scdn.co/spotify-player.js"></script>

// 2. Initialize player
window.onSpotifyWebPlaybackSDKReady = () => {
  const player = new Spotify.Player({
    name: 'Vibey Player',
    getOAuthToken: cb => { cb(spotifyAccessToken); },
    volume: 0.5
  });
  
  player.connect();
};
```

---

## API Keys Needed

### YouTube Data API v3

**Get Key:**
1. Go to https://console.cloud.google.com
2. Create project
3. Enable "YouTube Data API v3"
4. Create credentials (API Key)
5. Add to frontend `.env`:
   ```
   VITE_YOUTUBE_API_KEY=your_key_here
   ```

**Rate Limits:**
- 10,000 quota units/day (free tier)
- 1 search = 100 units
- = 100 searches per day (usually enough for MVP)

**Alternative: No API Key**
Use YouTube embeds without search:
```javascript
// Construct likely YouTube URL
const searchQuery = `${track.title} ${track.artist}`.replace(/ /g, '+');
const youtubeSearchUrl = `https://www.youtube.com/results?search_query=${searchQuery}`;
// Open in new tab or embed first result
```

---

## Backend Endpoints

### Check User Playback Capabilities

**GET /v1/me**
```json
{
  "user_id": "user_abc",
  "user_type": "spotify",  // or "guest"
  "has_spotify_premium": true,
  "playback_capabilities": {
    "spotify_preview": true,
    "spotify_premium": true,
    "youtube": true
  }
}
```

### Upgrade to Spotify Premium

**GET /v1/auth/spotify/login**
- Initiates OAuth flow
- User logs in with Spotify
- Backend checks if they have Premium
- Updates user_type to 'spotify'
- All future feeds return `playbackSource = "spotify_premium"`

---

## Track Data Flow

### 1. Track Seeding (Initial Setup)
```
CSV Dataset → Backend
  ├─ track_id (Spotify ID)
  ├─ title
  ├─ artist
  ├─ audio features
  └─ spotify_uri = "spotify:track:{track_id}"
```

### 2. Preview URL Update (On Deployment)
```
Backend → Spotify API
  ├─ Fetch preview_url for each track
  ├─ Fetch artwork_url
  └─ Update database
```

### 3. Feed Generation
```
User requests feed → Backend
  ├─ Check user_type (guest vs spotify)
  ├─ Generate recommendations
  ├─ For each track:
  │   ├─ Has Spotify Premium? → spotify_premium
  │   ├─ Has preview_url? → preview
  │   └─ Neither? → youtube
  └─ Return tracks with playbackSource
```

### 4. Frontend Playback
```
Frontend receives track
  ├─ playbackSource = "preview" → HTML5 audio
  ├─ playbackSource = "youtube" → YouTube search + embed
  └─ playbackSource = "spotify_premium" → Web Playback SDK
```

---

## Migration Path

### Phase 1: Current (MVP)
- ✅ Spotify previews (30s)
- ✅ YouTube fallback
- ⏳ Guest users only

### Phase 2: Spotify Integration
- ✅ OAuth login
- ✅ Detect Premium users
- ✅ Web Playback SDK for full tracks

### Phase 3: Enhanced
- Multi-source recommendations
- Offline playback (cache)
- Cross-fade between tracks
- Lyrics integration

---

## Example Frontend Component

```javascript
function TrackPlayer({ track }) {
  const [youtubeId, setYoutubeId] = useState(null);
  
  useEffect(() => {
    if (track.playbackSource === 'youtube') {
      searchYouTube(track.title, track.artist).then(setYoutubeId);
    }
  }, [track]);
  
  // Spotify Premium
  if (track.playbackSource === 'spotify_premium') {
    return <SpotifyPlayer uri={track.spotifyUri} />;
  }
  
  // Spotify Preview
  if (track.playbackSource === 'preview' && track.audioUrl) {
    return <audio src={track.audioUrl} controls />;
  }
  
  // YouTube Fallback
  if (track.playbackSource === 'youtube' && youtubeId) {
    return <YouTubeEmbed videoId={youtubeId} />;
  }
  
  return <div>Loading...</div>;
}
```

---

## Summary

✅ **All users get music:**
- Guest users: 30s previews + YouTube
- Premium users: Full Spotify tracks

✅ **Seamless experience:**
- Backend handles decision logic
- Frontend just follows `playbackSource`

✅ **Future-proof:**
- Easy to add more sources (SoundCloud, Apple Music)
- Modular playback system

**Current stats:** ~40% tracks have Spotify previews, 100% can use YouTube fallback!
