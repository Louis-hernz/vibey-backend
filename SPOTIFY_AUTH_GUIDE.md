# Spotify Premium Authentication - Frontend Guide

## Overview

Users can log in with Spotify to unlock **full-length track playback** (if they have Spotify Premium).

---

## User Flow

```
┌─────────────────────┐
│  Landing Screen     │
│                     │
│  [Continue as Guest]│  → Guest mode (previews + YouTube)
│  [Login with Spotify]│  → OAuth flow
└─────────────────────┘
           │
           │ Click "Login with Spotify"
           ▼
┌─────────────────────┐
│  Spotify Login Page │ (handled by Spotify)
│                     │
│  User logs in       │
│  Grants permissions │
└─────────────────────┘
           │
           │ Redirect back to app
           ▼
┌─────────────────────┐
│  App (Logged In)    │
│                     │
│  Welcome, {name}!   │
│  Premium: ✅ or ❌   │
└─────────────────────┘
```

---

## Backend Endpoints

### 1. Start OAuth Flow

**GET `/v1/auth/spotify/login`**

Redirects user to Spotify login page.

```javascript
// Frontend button click
<button onClick={() => {
  window.location.href = 'https://vibey-backend-production.up.railway.app/v1/auth/spotify/login';
}}>
  Login with Spotify
</button>
```

---

### 2. OAuth Callback (Automatic)

**GET `/v1/auth/spotify/callback`**

Spotify redirects here after login. Backend:
1. Exchanges auth code for tokens
2. Fetches user profile
3. Checks if user has Premium (`product: 'premium'`)
4. Creates/updates user in database
5. Sets session cookie
6. Redirects to frontend (`http://localhost:3000/` by default)

**You need to update the redirect URL!** See Configuration section below.

---

### 3. Get User Info

**GET `/v1/me`**

Returns current user data:

```json
{
  "user_id": "spotify_abc123",
  "user_type": "spotify",
  "spotify_user_id": "john_doe",
  "spotify_display_name": "John Doe",
  "has_spotify_premium": true,  // ← Check this!
  "created_at": 1703001234
}
```

---

## Frontend Implementation

### Landing Screen Component

```tsx
import React from 'react';

export function LandingScreen() {
  const handleGuestLogin = async () => {
    // Create guest user
    const response = await fetch('API_URL/v1/users', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
    
    const sessionId = response.headers.get('X-Session-Id');
    localStorage.setItem('session_id', sessionId);
    
    // Navigate to app
    window.location.href = '/app';
  };
  
  const handleSpotifyLogin = () => {
    // Save current location for redirect (optional)
    localStorage.setItem('pre_auth_location', window.location.pathname);
    
    // Redirect to Spotify OAuth
    window.location.href = 'https://vibey-backend-production.up.railway.app/v1/auth/spotify/login';
  };
  
  return (
    <div className="landing-screen">
      <h1>Welcome to Vibey</h1>
      <p>Discover music that matches your mood</p>
      
      <div className="auth-buttons">
        <button 
          onClick={handleSpotifyLogin}
          className="spotify-login-btn"
        >
          🎵 Login with Spotify
          <span className="subtitle">Full tracks with Premium</span>
        </button>
        
        <button 
          onClick={handleGuestLogin}
          className="guest-login-btn"
        >
          Continue as Guest
          <span className="subtitle">30s previews + YouTube</span>
        </button>
      </div>
    </div>
  );
}
```

---

### App Component (After Login)

```tsx
import React, { useEffect, useState } from 'react';

export function App() {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    fetchUserInfo();
  }, []);
  
  const fetchUserInfo = async () => {
    try {
      const sessionId = localStorage.getItem('session_id');
      
      const response = await fetch('API_URL/v1/me', {
        headers: {
          'X-Session-Id': sessionId
        }
      });
      
      if (response.ok) {
        const userData = await response.json();
        setUser(userData);
      } else {
        // No session - redirect to landing
        window.location.href = '/';
      }
    } catch (error) {
      console.error('Failed to fetch user:', error);
    } finally {
      setLoading(false);
    }
  };
  
  if (loading) return <div>Loading...</div>;
  
  return (
    <div className="app">
      <header>
        <h1>Vibey</h1>
        {user && (
          <div className="user-info">
            {user.spotify_display_name && (
              <span>Welcome, {user.spotify_display_name}!</span>
            )}
            {user.has_spotify_premium && (
              <span className="premium-badge">✨ Premium</span>
            )}
          </div>
        )}
      </header>
      
      {/* Your app content */}
      <TrackFeed user={user} />
    </div>
  );
}
```

---

### Handling OAuth Redirect

After Spotify login, backend redirects to `http://localhost:3000/`. You need to:

1. **Check for session cookie** (automatically set by backend)
2. **Fetch user info** to confirm login
3. **Show welcome message**

```tsx
// In your main App or routing component
useEffect(() => {
  // Check if we just came back from OAuth
  const urlParams = new URLSearchParams(window.location.search);
  
  if (window.location.pathname === '/' && !urlParams.has('code')) {
    // Normal load - check if user is logged in
    fetchUserInfo();
  }
}, []);
```

---

## Track Playback Based on User Type

```tsx
function TrackPlayer({ track, user }) {
  // Spotify Premium user
  if (user?.has_spotify_premium && track.playbackSource === 'spotify_premium') {
    return <SpotifyPremiumPlayer uri={track.spotifyUri} />;
  }
  
  // Spotify preview (30s)
  if (track.playbackSource === 'preview' && track.audioUrl) {
    return <audio src={track.audioUrl} controls />;
  }
  
  // YouTube fallback
  if (track.playbackSource === 'youtube') {
    return <YouTubePlayer track={track} />;
  }
  
  return <div>No playback available</div>;
}
```

---

## Configuration

### Update Redirect URL in Backend

In `main.py`, update the redirect URL to your Lovable app:

```python
# line 424
return RedirectResponse("https://your-lovable-app.lovable.app/")
```

Or make it configurable:

```python
# In config.py
class Settings(BaseSettings):
    ...
    frontend_url: str = "http://localhost:3000"

# In main.py
return RedirectResponse(settings.frontend_url)
```

Then set in Railway:
```
FRONTEND_URL=https://your-lovable-app.lovable.app
```

---

### Update Spotify Redirect URI

In Spotify Developer Dashboard:
1. Go to https://developer.spotify.com/dashboard
2. Click your app
3. Settings → Redirect URIs
4. Add: `https://vibey-backend-production.up.railway.app/v1/auth/spotify/callback`
5. Save

---

## Testing

### Test Guest Flow

1. Click "Continue as Guest"
2. Should create guest user
3. Feed shows `playbackSource: "preview"` or `"youtube"`

### Test Spotify Premium Flow

1. Click "Login with Spotify"
2. Log in with Premium account
3. Redirected back to app
4. GET `/v1/me` shows `has_spotify_premium: true`
5. Feed shows `playbackSource: "spotify_premium"`
6. Tracks have `spotifyUri` field

### Test Spotify Free Flow

1. Click "Login with Spotify"
2. Log in with Free account
3. GET `/v1/me` shows `has_spotify_premium: false`
4. Feed still shows `"preview"` or `"youtube"`
5. Same experience as guest

---

## Spotify Web Playback SDK (Premium Users)

For Premium users, integrate Spotify's Web Playback SDK:

### 1. Load SDK

```html
<!-- In index.html -->
<script src="https://sdk.scdn.co/spotify-player.js"></script>
```

### 2. Initialize Player

```javascript
window.onSpotifyWebPlaybackSDKReady = () => {
  const token = 'user_access_token';  // From your backend
  
  const player = new Spotify.Player({
    name: 'Vibey Player',
    getOAuthToken: cb => { cb(token); },
    volume: 0.5
  });

  // Error handling
  player.addListener('initialization_error', ({ message }) => {
    console.error(message);
  });

  player.addListener('authentication_error', ({ message }) => {
    console.error(message);
  });

  player.addListener('account_error', ({ message }) => {
    console.error(message);
  });

  player.addListener('playback_error', ({ message }) => {
    console.error(message);
  });

  // Ready
  player.addListener('ready', ({ device_id }) => {
    console.log('Ready with Device ID', device_id);
    
    // Play track
    player.activateElement().then(() => {
      // Player is ready
    });
  });

  // Connect to the player
  player.connect();
};
```

### 3. Play Tracks

```javascript
async function playTrack(spotifyUri, accessToken) {
  await fetch(`https://api.spotify.com/v1/me/player/play`, {
    method: 'PUT',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${accessToken}`
    },
    body: JSON.stringify({
      uris: [spotifyUri]
    })
  });
}
```

### 4. Get Access Token

You'll need to expose the user's Spotify access token:

**Add endpoint to backend:**

```python
@app.get("/v1/auth/spotify/token")
async def get_spotify_token(
    user_id: str = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Get user's Spotify access token for Web Playback SDK"""
    cursor = conn.cursor()
    cursor.execute("""
    SELECT spotify_access_token, spotify_token_expires_at, spotify_refresh_token
    FROM users WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row or not row[0]:
        raise HTTPException(status_code=404, detail="No Spotify token")
    
    # Check if token expired
    if row[1] < int(datetime.now().timestamp()):
        # Refresh token (TODO: implement refresh logic)
        pass
    
    return {
        "access_token": row[0],
        "expires_at": row[1]
    }
```

---

## Summary

✅ **Backend handles:**
- OAuth flow
- Token management  
- Premium detection
- User creation/migration

✅ **Frontend handles:**
- Login buttons
- Redirect handling
- User info display
- Playback based on user type

✅ **User experience:**
- Guest: Previews + YouTube
- Spotify Free: Previews + YouTube (logged in)
- Spotify Premium: Full tracks via Web Playback SDK

**Next:** Deploy backend, update redirect URLs, test the flow! 🎵
