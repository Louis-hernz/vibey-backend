# Frontend: Embedded YouTube Player Implementation

## Overview

This guide shows how to implement an embedded YouTube audio player in your Vibey frontend.

---

## Option 1: Using React-YouTube (Recommended)

### Install Package
```bash
npm install react-youtube
```

### Component Implementation

```tsx
import React, { useState, useEffect } from 'react';
import YouTube from 'react-youtube';

interface Track {
  trackId: string;
  title: string;
  artist: string;
  artworkUrl: string;
  audioUrl: string | null;
  playbackSource: 'preview' | 'youtube' | 'spotify_premium';
  spotifyUri: string | null;
}

export function TrackPlayer({ track }: { track: Track }) {
  const [youtubeVideoId, setYoutubeVideoId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // Fetch YouTube video ID when needed
  useEffect(() => {
    if (track.playbackSource === 'youtube') {
      fetchYouTubeVideo();
    }
  }, [track.trackId]);

  const fetchYouTubeVideo = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        `https://vibey-backend-production.up.railway.app/v1/youtube/search?title=${encodeURIComponent(track.title)}&artist=${encodeURIComponent(track.artist)}`
      );
      const data = await response.json();
      
      if (data.video_id) {
        setYoutubeVideoId(data.video_id);
      }
    } catch (error) {
      console.error('YouTube search failed:', error);
    } finally {
      setLoading(false);
    }
  };

  // Spotify Preview (30-second clip)
  if (track.playbackSource === 'preview' && track.audioUrl) {
    return (
      <div className="player-container">
        <audio 
          src={track.audioUrl} 
          controls 
          autoPlay
          className="w-full"
        />
      </div>
    );
  }

  // YouTube (full track)
  if (track.playbackSource === 'youtube') {
    if (loading) {
      return <div className="text-center p-4">Loading player...</div>;
    }

    if (youtubeVideoId) {
      return (
        <div className="player-container">
          <YouTube
            videoId={youtubeVideoId}
            opts={{
              height: '0',  // Hide video (audio only)
              width: '0',
              playerVars: {
                autoplay: 1,
                controls: 1,
                modestbranding: 1,
                rel: 0,
              },
            }}
            onReady={(event) => {
              // Player ready
              event.target.playVideo();
            }}
            onStateChange={(event) => {
              // Track state changes (playing, paused, ended)
              console.log('Player state:', event.data);
            }}
          />
          <div className="custom-controls">
            {/* Add custom UI controls here */}
            <p className="text-sm text-gray-600">Playing via YouTube</p>
          </div>
        </div>
      );
    }

    return (
      <div className="text-center p-4 text-gray-500">
        Preview unavailable
      </div>
    );
  }

  // Spotify Premium (future implementation)
  if (track.playbackSource === 'spotify_premium' && track.spotifyUri) {
    return (
      <div className="p-4 text-center">
        <p>Spotify Premium playback coming soon!</p>
        <p className="text-sm text-gray-600">{track.spotifyUri}</p>
      </div>
    );
  }

  return <div>No player available</div>;
}
```

---

## Option 2: Using YouTube IFrame API (No Dependencies)

### Load YouTube API

Add to your `index.html`:
```html
<script src="https://www.youtube.com/iframe_api"></script>
```

### Component Implementation

```tsx
import React, { useState, useEffect, useRef } from 'react';

export function YouTubePlayer({ track }) {
  const [videoId, setVideoId] = useState(null);
  const [player, setPlayer] = useState(null);
  const playerRef = useRef(null);

  useEffect(() => {
    if (track.playbackSource === 'youtube') {
      fetchYouTubeVideo();
    }
  }, [track.trackId]);

  useEffect(() => {
    if (videoId && !player) {
      // @ts-ignore
      const newPlayer = new window.YT.Player(playerRef.current, {
        height: '0',
        width: '0',
        videoId: videoId,
        playerVars: {
          autoplay: 1,
          controls: 0,
        },
        events: {
          onReady: (event) => {
            event.target.playVideo();
          },
          onStateChange: (event) => {
            // Handle state changes
          },
        },
      });
      setPlayer(newPlayer);
    }
  }, [videoId]);

  const fetchYouTubeVideo = async () => {
    const response = await fetch(
      `API_URL/v1/youtube/search?title=${encodeURIComponent(track.title)}&artist=${encodeURIComponent(track.artist)}`
    );
    const data = await response.json();
    if (data.video_id) {
      setVideoId(data.video_id);
    }
  };

  const handlePlay = () => player?.playVideo();
  const handlePause = () => player?.pauseVideo();

  if (track.playbackSource !== 'youtube') return null;

  return (
    <div>
      <div ref={playerRef}></div>
      <div className="controls">
        <button onClick={handlePlay}>Play</button>
        <button onClick={handlePause}>Pause</button>
      </div>
    </div>
  );
}
```

---

## Option 3: Simple iframe Embed (Easiest)

```tsx
export function SimpleYouTubePlayer({ track }) {
  const [videoId, setVideoId] = useState(null);

  useEffect(() => {
    if (track.playbackSource === 'youtube') {
      fetch(
        `API_URL/v1/youtube/search?title=${encodeURIComponent(track.title)}&artist=${encodeURIComponent(track.artist)}`
      )
        .then(res => res.json())
        .then(data => setVideoId(data.video_id));
    }
  }, [track.trackId]);

  if (track.playbackSource !== 'youtube' || !videoId) return null;

  return (
    <iframe
      width="100%"
      height="80"
      src={`https://www.youtube.com/embed/${videoId}?autoplay=1&controls=1`}
      frameBorder="0"
      allow="autoplay; encrypted-media"
      allowFullScreen
      className="youtube-player"
    />
  );
}
```

---

## Complete Track Card with Hybrid Player

```tsx
import React from 'react';
import { TrackPlayer } from './TrackPlayer';

export function TrackCard({ track, onLike, onDislike, onMoreLikeThis }) {
  return (
    <div className="track-card max-w-sm mx-auto bg-white rounded-lg shadow-lg overflow-hidden">
      {/* Album Artwork */}
      <div className="artwork-container relative h-80">
        <img 
          src={track.artworkUrl || 'https://via.placeholder.com/300'} 
          alt={`${track.title} artwork`}
          className="w-full h-full object-cover"
        />
        
        {/* Playback Source Badge */}
        <div className="absolute top-4 right-4 bg-black bg-opacity-70 text-white px-3 py-1 rounded-full text-xs">
          {track.playbackSource === 'preview' && '30s Preview'}
          {track.playbackSource === 'youtube' && 'YouTube'}
          {track.playbackSource === 'spotify_premium' && 'Spotify Premium'}
        </div>
      </div>

      {/* Track Info */}
      <div className="p-6">
        <h2 className="text-2xl font-bold mb-2">{track.title}</h2>
        <p className="text-gray-600 mb-4">{track.artist}</p>
        
        {/* Vibe Tags */}
        <div className="flex flex-wrap gap-2 mb-4">
          {track.vibeTags.map(vibe => (
            <span 
              key={vibe}
              className="px-3 py-1 bg-purple-100 text-purple-700 rounded-full text-sm"
            >
              {vibe}
            </span>
          ))}
        </div>

        {/* Audio Player */}
        <div className="mb-6">
          <TrackPlayer track={track} />
        </div>

        {/* Action Buttons */}
        <div className="flex justify-between items-center">
          <button 
            onClick={onDislike}
            className="p-4 rounded-full bg-red-100 hover:bg-red-200 transition"
          >
            👎
          </button>
          
          <button 
            onClick={onMoreLikeThis}
            className="p-4 rounded-full bg-yellow-100 hover:bg-yellow-200 transition"
          >
            ⭐
          </button>
          
          <button 
            onClick={onLike}
            className="p-4 rounded-full bg-green-100 hover:bg-green-200 transition"
          >
            ❤️
          </button>
        </div>
      </div>
    </div>
  );
}
```

---

## Environment Setup

### Backend (Railway)

**Optional:** Add YouTube API key to enable server-side search
```env
YOUTUBE_API_KEY=your_youtube_api_key_here
```

### Frontend

```env
VITE_API_URL=https://vibey-backend-production.up.railway.app
VITE_YOUTUBE_API_KEY=your_youtube_api_key_here  # Optional
```

---

## How to Get YouTube API Key

1. Go to https://console.cloud.google.com
2. Create a new project
3. Enable "YouTube Data API v3"
4. Go to Credentials → Create Credentials → API Key
5. Copy the API key
6. (Optional) Restrict key to YouTube Data API v3

**Note:** Frontend can call backend's `/v1/youtube/search` endpoint which handles API key server-side (more secure).

---

## Styling the Player

### Hide Video, Show Custom Controls

```css
.youtube-player iframe {
  display: none;  /* Hide video */
}

.custom-controls {
  padding: 1rem;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 12px;
  color: white;
}

.custom-controls button {
  background: rgba(255, 255, 255, 0.2);
  border: none;
  padding: 0.5rem 1rem;
  border-radius: 8px;
  color: white;
  cursor: pointer;
  margin: 0 0.5rem;
}

.custom-controls button:hover {
  background: rgba(255, 255, 255, 0.3);
}
```

---

## Testing

### Test Different Playback Modes

```javascript
// Mock tracks for testing
const tracks = [
  // Spotify preview
  {
    trackId: '1',
    title: 'Blinding Lights',
    artist: 'The Weeknd',
    playbackSource: 'preview',
    audioUrl: 'https://p.scdn.co/mp3-preview/...'
  },
  
  // YouTube fallback
  {
    trackId: '2',
    title: 'Bohemian Rhapsody',
    artist: 'Queen',
    playbackSource: 'youtube',
    audioUrl: null
  },
];
```

---

## Summary

✅ **Embedded YouTube player** - No external links needed  
✅ **Seamless experience** - Plays within your app  
✅ **Custom controls** - Design your own UI  
✅ **Hybrid playback** - Spotify previews + YouTube fallback  

**Recommended:** Use **react-youtube** package (Option 1) for easiest implementation with good API.

**Next:** Deploy backend changes and implement in Lovable using the code examples above! 🎵
