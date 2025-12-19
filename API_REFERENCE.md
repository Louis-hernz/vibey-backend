# Vibey API Quick Reference

## Base URL
```
http://localhost:8000
```

## Quick Start

### 1. Create a User
```bash
curl -X POST http://localhost:8000/v1/users -c cookies.txt
```

Save the cookies for subsequent requests.

### 2. Get Available Vibes
```bash
curl http://localhost:8000/v1/vibes
```

### 3. Get Explore Feed
```bash
curl "http://localhost:8000/v1/feed/next?mode=explore&limit=10" -b cookies.txt
```

### 4. Submit Feedback
```bash
curl -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"track_id": "TRACK_ID", "action": "like"}' \
  -b cookies.txt
```

### 5. Get Vibe-Specific Feed
```bash
curl "http://localhost:8000/v1/feed/next?mode=vibe&vibe_id=1&limit=10" -b cookies.txt
```

## All Endpoints

### Users

#### Create Guest User
```http
POST /v1/users
```
**Response:**
```json
{
  "user_id": "guest_abc123",
  "user_type": "guest",
  "created_at": 1234567890
}
```

#### Get Current User
```http
GET /v1/me
```

### Authentication

#### Spotify Login
```http
GET /v1/auth/spotify/login
```
Redirects to Spotify OAuth.

#### Spotify Callback
```http
GET /v1/auth/spotify/callback?code=XXX&state=YYY
```

### Vibes

#### Get All Vibes
```http
GET /v1/vibes
```

**Response:**
```json
[
  {
    "vibe_id": 1,
    "name": "energetic",
    "description": "High energy, intense and powerful",
    "color": "#FF6B6B"
  }
]
```

### Feed

#### Get Personalized Feed

**Explore Mode** (only unseen tracks):
```http
GET /v1/feed/next?mode=explore&limit=10&seed=42
```

**Vibe Mode** (mix of liked and unseen in a vibe):
```http
GET /v1/feed/next?mode=vibe&vibe_id=2&limit=10
```

**Parameters:**
- `mode` (required): "explore" or "vibe"
- `vibe_id` (required if mode=vibe): Integer vibe ID
- `limit` (optional): 1-50, default 10
- `seed` (optional): Integer for deterministic results

**Response:**
```json
{
  "tracks": [
    {
      "trackId": "3n3Ppam7vgaVa1iaRUc9Lp",
      "title": "Mr. Brightside",
      "artist": "The Killers",
      "artworkUrl": "https://i.scdn.co/image/...",
      "audioUrl": "https://p.scdn.co/mp3-preview/...",
      "source": "spotify",
      "vibeTags": ["energetic", "upbeat"]
    }
  ],
  "mode": "explore",
  "vibe_id": null
}
```

### Feedback

#### Submit Feedback
```http
POST /v1/feedback
Content-Type: application/json

{
  "track_id": "3n3Ppam7vgaVa1iaRUc9Lp",
  "action": "like"
}
```

**Actions:**
- `like`: Positive feedback, moves preference toward track
- `dislike`: Negative feedback, moves preference away from track
- `more_like_this`: Stronger positive feedback
- `undo`: Reverts last feedback action

**Response:**
```json
{
  "success": true,
  "feedback_id": 123,
  "message": "Feedback 'like' applied"
}
```

### History

#### Get Feedback History
```http
GET /v1/history?limit=50
```

**Response:**
```json
{
  "items": [
    {
      "feedback_id": 123,
      "track": { /* TrackResponse */ },
      "action": "like",
      "created_at": 1234567890,
      "undone": false
    }
  ],
  "total": 123
}
```

## Example Workflows

### New User Flow

```bash
# 1. Create user
curl -X POST http://localhost:8000/v1/users -c cookies.txt

# 2. Get first explore feed
curl "http://localhost:8000/v1/feed/next?mode=explore&limit=5" -b cookies.txt

# 3. Like a track
curl -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"track_id": "TRACK_ID", "action": "like"}' \
  -b cookies.txt

# 4. Get next feed (influenced by preference)
curl "http://localhost:8000/v1/feed/next?mode=explore&limit=5" -b cookies.txt
```

### Vibe Exploration Flow

```bash
# 1. Get available vibes
curl http://localhost:8000/v1/vibes -b cookies.txt

# 2. Get feed for a specific vibe
curl "http://localhost:8000/v1/feed/next?mode=vibe&vibe_id=2&limit=10" -b cookies.txt

# 3. Like tracks you enjoy
curl -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"track_id": "TRACK_ID", "action": "like"}' \
  -b cookies.txt

# 4. Get more from same vibe (now includes liked tracks)
curl "http://localhost:8000/v1/feed/next?mode=vibe&vibe_id=2&limit=10" -b cookies.txt
```

### Testing Determinism

```bash
# Get feed with seed twice - should be identical
curl "http://localhost:8000/v1/feed/next?mode=explore&seed=42&limit=5" -b cookies.txt
curl "http://localhost:8000/v1/feed/next?mode=explore&seed=42&limit=5" -b cookies.txt

# Compare outputs - track IDs should match
```

## Python Example

```python
import requests

BASE_URL = "http://localhost:8000"
session = requests.Session()

# Create user
response = session.post(f"{BASE_URL}/v1/users")
user = response.json()
print(f"Created user: {user['user_id']}")

# Get vibes
vibes = session.get(f"{BASE_URL}/v1/vibes").json()
print(f"Available vibes: {[v['name'] for v in vibes]}")

# Get explore feed
feed = session.get(
    f"{BASE_URL}/v1/feed/next",
    params={"mode": "explore", "limit": 5}
).json()

print(f"Got {len(feed['tracks'])} tracks")

# Like first track
if feed['tracks']:
    track = feed['tracks'][0]
    response = session.post(
        f"{BASE_URL}/v1/feedback",
        json={"track_id": track['trackId'], "action": "like"}
    )
    print(f"Liked: {track['title']} by {track['artist']}")

# Get history
history = session.get(f"{BASE_URL}/v1/history").json()
print(f"Feedback history: {history['total']} items")
```

## JavaScript Example

```javascript
const BASE_URL = 'http://localhost:8000';

async function main() {
  // Create user
  const userResponse = await fetch(`${BASE_URL}/v1/users`, {
    method: 'POST',
    credentials: 'include'
  });
  const user = await userResponse.json();
  console.log('Created user:', user.user_id);

  // Get explore feed
  const feedResponse = await fetch(
    `${BASE_URL}/v1/feed/next?mode=explore&limit=5`,
    { credentials: 'include' }
  );
  const feed = await feedResponse.json();
  console.log('Got tracks:', feed.tracks.length);

  // Like first track
  if (feed.tracks.length > 0) {
    const track = feed.tracks[0];
    await fetch(`${BASE_URL}/v1/feedback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({
        track_id: track.trackId,
        action: 'like'
      })
    });
    console.log('Liked:', track.title);
  }
}

main();
```

## Status Codes

- `200 OK`: Request successful
- `400 Bad Request`: Invalid parameters
- `401 Unauthorized`: Authentication required
- `404 Not Found`: Resource not found
- `500 Internal Server Error`: Server error

## Rate Limiting

Currently no rate limiting implemented. In production, consider:
- 100 requests/minute per user
- 1000 requests/hour per IP

## CORS

Configured for:
- `http://localhost:3000`
- `http://localhost:5173`
- `https://*.lovable.app`
- `https://*.lovable.dev`

## Authentication

Uses session cookies (`vibey_session`):
- HttpOnly (not accessible via JavaScript)
- SameSite: Lax
- Max age: 30 days

## Notes

- All timestamps are Unix timestamps (seconds since epoch)
- Track IDs are Spotify track IDs
- Embedding dimension is configurable (default 128)
- Preference vectors are automatically normalized
- Feedback history stores the exact delta applied
