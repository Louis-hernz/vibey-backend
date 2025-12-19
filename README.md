# Vibey Backend API

A music exploration and recommendation API built with FastAPI, featuring preference-based learning and Spotify integration.

## Features

- 🎵 **Personalized Recommendations**: Uses embedding vectors and online learning from user feedback
- 🎭 **Vibe-Based Discovery**: Categorizes music into vibes (energetic, chill, melancholic, etc.)
- 🔐 **Dual User System**: Supports anonymous guest users and Spotify OAuth
- 📊 **Real Spotify Data**: Fetches tracks and audio features from Spotify API
- 🎯 **Smart Feed Generation**: 
  - Explore mode: Only new/unseen tracks
  - Vibe mode: Mix of liked and new tracks within a vibe
- 💾 **Feedback System**: Like, dislike, more_like_this, and undo actions
- 🔄 **Preference Vector Updates**: Real-time learning from user interactions

## Tech Stack

- **Framework**: FastAPI 0.104
- **Database**: SQLite (easy to migrate to PostgreSQL)
- **ML**: NumPy for vector operations
- **API Integration**: Spotipy for Spotify API
- **Auth**: Session-based with HTTPOnly cookies

## Project Structure

```
vibey-backend/
├── main.py              # FastAPI application with all endpoints
├── config.py            # Configuration and tunable parameters
├── database.py          # Database schema and initialization
├── models.py            # Pydantic models for API
├── recommender.py       # Recommendation engine
├── spotify_client.py    # Spotify API integration
├── seed_tracks.py       # Script to populate database
├── requirements.txt     # Python dependencies
└── .env.example         # Environment variables template
```

## Setup Instructions

### 1. Clone and Install Dependencies

```bash
cd vibey-backend
pip install -r requirements.txt
```

### 2. Get Spotify API Credentials

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Note your Client ID and Client Secret
4. Add redirect URI: `http://localhost:8000/v1/auth/spotify/callback`

### 3. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` and add your Spotify credentials:

```env
SPOTIFY_CLIENT_ID=your_actual_client_id
SPOTIFY_CLIENT_SECRET=your_actual_client_secret
```

### 4. Initialize Database

```bash
python database.py
```

This creates the SQLite database and seeds the vibe taxonomy.

### 5. Seed Tracks (Optional but Recommended)

Fetch 500 tracks from Spotify with audio features:

```bash
python seed_tracks.py 500
```

This will:
- Fetch tracks from popular Spotify playlists
- Get audio features for each track
- Generate embedding vectors from audio features
- Assign vibe tags based on features
- Store everything in the database

**Note**: This requires valid Spotify credentials.

### 6. Run the Server

```bash
python main.py
```

Or with uvicorn directly:

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

### Interactive Docs

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Endpoints

#### User Management

**Create Guest User**
```http
POST /v1/users
```

Creates an anonymous user and returns a session cookie.

Response:
```json
{
  "user_id": "guest_abc123",
  "user_type": "guest",
  "created_at": 1234567890
}
```

**Get Current User**
```http
GET /v1/me
```

Returns current authenticated user info.

#### Authentication

**Spotify Login**
```http
GET /v1/auth/spotify/login
```

Redirects to Spotify OAuth page.

**Spotify Callback**
```http
GET /v1/auth/spotify/callback?code=...&state=...
```

Handles OAuth callback, creates/updates user, and sets session cookie.

#### Vibes

**Get All Vibes**
```http
GET /v1/vibes
```

Response:
```json
[
  {
    "vibe_id": 1,
    "name": "energetic",
    "description": "High energy, intense and powerful",
    "color": "#FF6B6B"
  },
  ...
]
```

#### Feed Generation

**Get Personalized Feed**
```http
GET /v1/feed/next?mode=explore&limit=10&seed=42
GET /v1/feed/next?mode=vibe&vibe_id=2&limit=10
```

Parameters:
- `mode` (required): "explore" or "vibe"
- `vibe_id` (required for vibe mode): ID of the vibe
- `limit` (optional): Number of tracks (1-50, default 10)
- `seed` (optional): Random seed for deterministic results

Response:
```json
{
  "tracks": [
    {
      "trackId": "spotify_track_id",
      "title": "Song Title",
      "artist": "Artist Name",
      "artworkUrl": "https://...",
      "audioUrl": "https://...",
      "source": "spotify",
      "vibeTags": ["energetic", "party"]
    }
  ],
  "mode": "explore",
  "vibe_id": null
}
```

#### Feedback

**Submit Feedback**
```http
POST /v1/feedback
Content-Type: application/json

{
  "track_id": "spotify_track_id",
  "action": "like"
}
```

Actions: `like`, `dislike`, `more_like_this`, `undo`

Response:
```json
{
  "success": true,
  "feedback_id": 123,
  "message": "Feedback 'like' applied"
}
```

#### History

**Get Feedback History**
```http
GET /v1/history?limit=50
```

Response:
```json
{
  "items": [
    {
      "feedback_id": 123,
      "track": { ... },
      "action": "like",
      "created_at": 1234567890,
      "undone": false
    }
  ],
  "total": 123
}
```

## How the Recommender Works

### 1. Embedding Vectors

Each track has a 128-dimensional embedding vector derived from Spotify audio features:
- acousticness
- danceability
- energy
- instrumentalness
- liveness
- loudness
- speechiness
- valence
- tempo

These are normalized and projected to 128 dimensions.

### 2. User Preference Vector

Each user has a preference vector (same dimension) that represents their musical taste. It starts at zero (neutral) and updates based on feedback.

### 3. Update Rules

When a user provides feedback:
- **Like**: `p = normalize(p + α * e(t))`
- **Dislike**: `p = normalize(p - β * e(t))`
- **More Like This**: `p = normalize(p + γ * e(t))` (stronger than like)
- **Undo**: Reverts the last preference update

Default learning rates: α=0.3, β=0.5, γ=0.6 (configurable in `.env`)

### 4. Feed Generation

**Explore Mode**:
1. Get all unseen tracks
2. Sample N×5 candidates randomly
3. Score each with dot product: `score = p · e(t)`
4. Apply diversity penalty (reduce score for over-represented artists)
5. Return top N tracks

**Vibe Mode**:
1. Filter tracks by vibe tag
2. Get 60% from explicitly liked tracks (random sample)
3. Get 40% from unseen tracks, scored by similarity to preference
4. Shuffle and return

### 5. Vibe Assignment

Tracks are automatically tagged with vibes based on audio features:
- **Energetic**: high energy + high danceability
- **Chill**: low energy + high acousticness
- **Melancholic**: low valence + low energy
- **Upbeat**: high valence + moderate-high energy
- **Focus**: high instrumentalness + moderate energy
- **Party**: high danceability + high energy + high valence

## Configuration

All tunable parameters are in `.env`:

```env
# Embedding dimension
EMBEDDING_DIM=128

# Learning rates
ALPHA_LIKE=0.3          # Like feedback strength
BETA_DISLIKE=0.5        # Dislike feedback strength
GAMMA_MORE_LIKE=0.6     # More-like-this strength

# Feed generation
DEFAULT_FEED_SIZE=10
EXPLORE_CANDIDATE_MULTIPLIER=5  # Sample N×5 candidates
VIBE_UNSEEN_RATIO=0.4          # 40% unseen, 60% liked in vibe mode
DIVERSITY_ARTIST_PENALTY=0.3    # Artist frequency penalty

# Initial user preferences
INITIAL_PREFERENCE_MODE=zero    # zero, random, or mean
```

## Testing

### Deterministic Feeds

Use the `seed` parameter for reproducible results:

```bash
curl "http://localhost:8000/v1/feed/next?mode=explore&seed=42"
```

Same seed = same feed for that user state.

### Manual Testing

1. Create a guest user:
```bash
curl -X POST http://localhost:8000/v1/users -c cookies.txt
```

2. Get explore feed:
```bash
curl http://localhost:8000/v1/feed/next?mode=explore -b cookies.txt
```

3. Submit feedback:
```bash
curl -X POST http://localhost:8000/v1/feedback \
  -H "Content-Type: application/json" \
  -d '{"track_id": "track_id_here", "action": "like"}' \
  -b cookies.txt
```

4. Get vibe feed:
```bash
curl "http://localhost:8000/v1/feed/next?mode=vibe&vibe_id=1" -b cookies.txt
```

## Database Schema

### Tables

- **users**: User accounts (guest or Spotify)
- **sessions**: Session management for authentication
- **tracks**: Music tracks with embeddings
- **vibes**: Vibe taxonomy
- **track_vibes**: Many-to-many relationship
- **feedback**: User feedback log with preference deltas
- **seen_tracks**: Tracks user has seen (for explore mode)
- **audio_features**: Cached Spotify audio features

### Key Indexes

- User lookups by Spotify ID
- Session expiration checks
- Feedback by user and track
- Seen tracks by user
- Track-vibe relationships

## Production Considerations

1. **Switch to PostgreSQL**: Update `DATABASE_URL` in `.env`
2. **Use Redis for sessions**: Implement session store in Redis
3. **Add rate limiting**: Protect endpoints from abuse
4. **Enable HTTPS**: Use SSL certificates
5. **Refresh Spotify tokens**: Implement background job to refresh expired tokens
6. **Scale recommendations**: Use vector database (Pinecone, Qdrant) for large catalogs
7. **Add monitoring**: Integrate Sentry or similar
8. **Cache audio features**: Reduce Spotify API calls

## Troubleshooting

### No tracks in database
Run `python seed_tracks.py 500` to populate with Spotify tracks.

### Spotify API errors
Check your credentials in `.env` and ensure redirect URI matches in Spotify dashboard.

### Empty feeds
User might have seen all tracks. Either:
- Add more tracks to database
- Adjust `EXPLORE_CANDIDATE_MULTIPLIER`
- Reset user's seen tracks

### Session issues
Sessions expire after 30 days. User needs to create new session or re-authenticate.

## License

MIT

## Support

For issues or questions, please open an issue on the repository.
