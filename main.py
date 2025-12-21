from fastapi import FastAPI, HTTPException, Cookie, Response, Query, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Optional, List
import sqlite3
import secrets
import uuid
from datetime import datetime, timedelta
import numpy as np
from itsdangerous import URLSafeTimedSerializer

from config import settings
from database import Database, vector_to_json, json_to_vector
from models import (
    UserCreate, UserResponse, VibeResponse, TrackResponse,
    FeedRequest, FeedResponse, FeedbackRequest, FeedbackResponse,
    HistoryItem, HistoryResponse, ErrorResponse
)
from spotify_client import spotify_client
from recommender import RecommenderEngine

# Initialize FastAPI app
app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="Music exploration and recommendation API"
)

# CORS middleware
cors_origins = settings.cors_origins.split(",") if settings.cors_origins else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Session serializer
session_serializer = URLSafeTimedSerializer(settings.secret_key)

# Database connection
db = Database()


def get_db():
    """Get database connection"""
    conn = db.connect()
    try:
        yield conn
    finally:
        conn.close()


def get_current_user(
    vibey_session: Optional[str] = Cookie(None),
    x_session_id: Optional[str] = Header(None),
    conn: sqlite3.Connection = Depends(get_db)
) -> Optional[str]:
    """Get current user from session cookie or header"""
    session_id = vibey_session or x_session_id
    
    if not session_id:
        return None
    
    try:
        # Verify session
        cursor = conn.cursor()
        cursor.execute("""
        SELECT user_id, expires_at FROM sessions WHERE session_id = ?
        """, (session_id,))
        row = cursor.fetchone()
        
        if not row:
            return None
        
        user_id, expires_at = row
        
        # Check if expired
        if expires_at < int(datetime.now().timestamp()):
            return None
        
        return user_id
    except Exception:
        return None


def require_user(user_id: Optional[str] = Depends(get_current_user)) -> str:
    """Require authenticated user"""
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user_id


def create_session(user_id: str, conn: sqlite3.Connection) -> str:
    """Create new session for user"""
    session_id = secrets.token_urlsafe(32)
    timestamp = int(datetime.now().timestamp())
    expires_at = timestamp + settings.session_max_age
    
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO sessions (session_id, user_id, created_at, expires_at)
    VALUES (?, ?, ?, ?)
    """, (session_id, user_id, timestamp, expires_at))
    conn.commit()
    
    return session_id


@app.on_event("startup")
async def startup_event():
    """Initialize database on startup"""
    db.init_db()
    db.seed_vibes()


@app.get("/")
async def root():
    """API root"""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "endpoints": {
            "users": "/v1/users",
            "auth": "/v1/auth/spotify/login",
            "vibes": "/v1/vibes",
            "feed": "/v1/feed/next",
            "feedback": "/v1/feedback",
            "history": "/v1/history",
            "admin": "/admin/update-previews"
        }
    }


@app.get("/admin/update-previews")
async def update_preview_urls(limit: int = 100):
    """Update preview URLs from Spotify API"""
    import httpx
    import asyncio
    
    # Get Spotify access token
    auth_url = "https://accounts.spotify.com/api/token"
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret
    }
    
    async with httpx.AsyncClient() as client:
        try:
            auth_response = await client.post(auth_url, data=auth_data)
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get Spotify token: {e}")
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Get database connection
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get tracks without preview URLs
        cursor.execute("""
        SELECT track_id, title, artist FROM tracks 
        WHERE (preview_url IS NULL OR preview_url = '') 
        AND track_id IS NOT NULL
        LIMIT ?
        """, (limit,))
        
        tracks = cursor.fetchall()
        
        updated_count = 0
        failed_count = 0
        updates = []
        
        for track_id, title, artist in tracks:
            try:
                track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
                response = await client.get(track_url, headers=headers)
                
                if response.status_code != 200:
                    failed_count += 1
                    continue
                
                track_info = response.json()
                preview_url = track_info.get('preview_url')
                album_art = None
                
                if track_info.get('album') and track_info['album'].get('images'):
                    images = track_info['album']['images']
                    if images:
                        album_art = images[0]['url']
                
                if preview_url or album_art:
                    cursor.execute("""
                    UPDATE tracks 
                    SET preview_url = ?, 
                        audio_url = ?,
                        artwork_url = ?
                    WHERE track_id = ?
                    """, (preview_url, preview_url, album_art or "https://via.placeholder.com/300", track_id))
                    
                    updated_count += 1
                    updates.append({
                        "track": f"{title} - {artist}",
                        "has_preview": preview_url is not None,
                        "has_artwork": album_art is not None
                    })
                else:
                    failed_count += 1
                
                await asyncio.sleep(0.35)
                
            except Exception as e:
                failed_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        return {
            "success": True,
            "updated": updated_count,
            "failed": failed_count,
            "total_processed": len(tracks),
            "sample_updates": updates[:10],
            "message": f"Run this endpoint {(997 // limit) + 1} times to update all tracks"
        }


@app.post("/v1/users", response_model=UserResponse)
async def create_user(
    response: Response,
    user_data: UserCreate = None,
    conn: sqlite3.Connection = Depends(get_db)
):
    """Create a new guest user"""
    user_id = f"guest_{uuid.uuid4().hex[:12]}"
    timestamp = int(datetime.now().timestamp())
    
    # Initialize with zero preference vector
    initial_pref = np.zeros(settings.embedding_dim)
    
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO users (user_id, user_type, preference_vector, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?)
    """, (user_id, 'guest', vector_to_json(initial_pref), timestamp, timestamp))
    conn.commit()
    
    # Create session
    session_id = create_session(user_id, conn)
    
    # Set session cookie
    response.set_cookie(
        key=settings.session_cookie_name,
        value=session_id,
        max_age=settings.session_max_age,
        httponly=True,
        samesite="none",  # Allow cross-site cookies
        secure=True  # Required for SameSite=None
    )
    
    # Also return session_id in response for header-based auth
    response.headers["X-Session-Id"] = session_id
    
    return UserResponse(
        user_id=user_id,
        user_type='guest',
        created_at=timestamp
    )


@app.get("/v1/auth/spotify/login")
async def spotify_login(
    vibey_session: Optional[str] = Cookie(None),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Initiate Spotify OAuth flow"""
    # Generate state token
    state = secrets.token_urlsafe(32)
    
    # Store state with user session if exists
    if vibey_session:
        user_id = get_current_user(vibey_session, conn)
        if user_id:
            # Store state temporarily (you might want a states table)
            pass
    
    # Get Spotify OAuth URL
    auth_url = spotify_client.get_oauth_url(state)
    
    return RedirectResponse(auth_url)


@app.get("/v1/auth/spotify/callback")
async def spotify_callback(
    code: str,
    state: str,
    response: Response,
    vibey_session: Optional[str] = Cookie(None),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Handle Spotify OAuth callback"""
    try:
        # Exchange code for token
        token_info = spotify_client.exchange_code(code)
        access_token = token_info['access_token']
        refresh_token = token_info['refresh_token']
        expires_in = token_info['expires_in']
        expires_at = int(datetime.now().timestamp()) + expires_in
        
        # Get user profile
        profile = spotify_client.get_user_profile(access_token)
        spotify_user_id = profile['id']
        
        cursor = conn.cursor()
        timestamp = int(datetime.now().timestamp())
        
        # Check if Spotify user already exists
        cursor.execute("""
        SELECT user_id FROM users WHERE spotify_user_id = ?
        """, (spotify_user_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing user
            user_id = existing[0]
            cursor.execute("""
            UPDATE users 
            SET spotify_access_token = ?,
                spotify_refresh_token = ?,
                spotify_token_expires_at = ?,
                updated_at = ?
            WHERE user_id = ?
            """, (access_token, refresh_token, expires_at, timestamp, user_id))
        else:
            # Check if we should migrate a guest user
            guest_user_id = None
            if vibey_session:
                guest_user_id = get_current_user(vibey_session, conn)
                if guest_user_id and guest_user_id.startswith('guest_'):
                    # Migrate guest to Spotify user
                    cursor.execute("""
                    UPDATE users
                    SET user_type = 'spotify',
                        spotify_user_id = ?,
                        spotify_access_token = ?,
                        spotify_refresh_token = ?,
                        spotify_token_expires_at = ?,
                        updated_at = ?
                    WHERE user_id = ?
                    """, (spotify_user_id, access_token, refresh_token, expires_at, 
                          timestamp, guest_user_id))
                    user_id = guest_user_id
                else:
                    guest_user_id = None
            
            if not guest_user_id:
                # Create new Spotify user
                user_id = f"spotify_{uuid.uuid4().hex[:12]}"
                initial_pref = np.zeros(settings.embedding_dim)
                
                cursor.execute("""
                INSERT INTO users 
                (user_id, user_type, spotify_user_id, spotify_access_token,
                 spotify_refresh_token, spotify_token_expires_at, 
                 preference_vector, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (user_id, 'spotify', spotify_user_id, access_token, 
                      refresh_token, expires_at, vector_to_json(initial_pref),
                      timestamp, timestamp))
        
        conn.commit()
        
        # Create new session
        session_id = create_session(user_id, conn)
        
        # Set session cookie
        response.set_cookie(
            key=settings.session_cookie_name,
            value=session_id,
            max_age=settings.session_max_age,
            httponly=True,
            samesite="none",
            secure=True
        )
        
        # Redirect to frontend
        return RedirectResponse("http://localhost:3000/")
    
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")


@app.get("/v1/vibes", response_model=List[VibeResponse])
async def get_vibes(conn: sqlite3.Connection = Depends(get_db)):
    """Get all available vibes"""
    cursor = conn.cursor()
    cursor.execute("SELECT vibe_id, name, description, color FROM vibes ORDER BY name")
    
    vibes = []
    for row in cursor.fetchall():
        vibes.append(VibeResponse(
            vibe_id=row[0],
            name=row[1],
            description=row[2],
            color=row[3]
        ))
    
    return vibes


@app.get("/v1/feed/next", response_model=FeedResponse)
async def get_feed(
    mode: str = Query(..., regex="^(explore|vibe)$"),
    vibe_id: Optional[int] = None,
    limit: int = Query(10, ge=1, le=50),
    seed: Optional[int] = None,
    user_id: str = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Generate personalized feed"""
    # Validate vibe mode
    if mode == "vibe" and not vibe_id:
        raise HTTPException(status_code=400, detail="vibe_id required for vibe mode")
    
    # Initialize recommender
    recommender = RecommenderEngine(conn)
    
    # Generate feed
    if mode == "explore":
        track_ids = recommender.generate_explore_feed(user_id, limit, seed)
    else:
        track_ids = recommender.generate_vibe_feed(user_id, vibe_id, limit, seed)
    
    # Mark tracks as seen
    recommender.mark_tracks_seen(user_id, track_ids)
    
    # Fetch track details
    cursor = conn.cursor()
    tracks = []
    
    for track_id in track_ids:
        cursor.execute("""
        SELECT t.track_id, t.title, t.artist, t.artwork_url, t.audio_url, t.source
        FROM tracks t
        WHERE t.track_id = ?
        """, (track_id,))
        
        row = cursor.fetchone()
        if row:
            # Get vibe tags
            cursor.execute("""
            SELECT v.name
            FROM vibes v
            INNER JOIN track_vibes tv ON v.vibe_id = tv.vibe_id
            WHERE tv.track_id = ?
            """, (track_id,))
            
            vibe_tags = [r[0] for r in cursor.fetchall()]
            
            tracks.append(TrackResponse(
                trackId=row[0],
                title=row[1],
                artist=row[2],
                artworkUrl=row[3],
                audioUrl=row[4],
                source=row[5],
                vibeTags=vibe_tags
            ))
    
    return FeedResponse(
        tracks=tracks,
        mode=mode,
        vibe_id=vibe_id
    )


@app.post("/v1/feedback", response_model=FeedbackResponse)
async def submit_feedback(
    feedback: FeedbackRequest,
    user_id: str = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Submit feedback on a track"""
    recommender = RecommenderEngine(conn)
    
    try:
        if feedback.action == "undo":
            # Undo last feedback
            success = recommender.undo_feedback(user_id)
            if not success:
                raise HTTPException(status_code=400, detail="No feedback to undo")
            
            return FeedbackResponse(
                success=True,
                message="Feedback undone"
            )
        else:
            # Apply feedback
            delta, feedback_id = recommender.apply_feedback(
                user_id, feedback.track_id, feedback.action
            )
            
            return FeedbackResponse(
                success=True,
                feedback_id=feedback_id,
                message=f"Feedback '{feedback.action}' applied"
            )
    
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing feedback: {str(e)}")


@app.get("/v1/history", response_model=HistoryResponse)
async def get_history(
    limit: int = Query(50, ge=1, le=200),
    user_id: str = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Get user's feedback history"""
    cursor = conn.cursor()
    
    cursor.execute("""
    SELECT f.feedback_id, f.track_id, f.action, f.created_at, f.undone,
           t.title, t.artist, t.artwork_url, t.audio_url, t.source
    FROM feedback f
    INNER JOIN tracks t ON f.track_id = t.track_id
    WHERE f.user_id = ?
    ORDER BY f.created_at DESC
    LIMIT ?
    """, (user_id, limit))
    
    items = []
    for row in cursor.fetchall():
        # Get vibe tags
        cursor.execute("""
        SELECT v.name
        FROM vibes v
        INNER JOIN track_vibes tv ON v.vibe_id = tv.vibe_id
        WHERE tv.track_id = ?
        """, (row[1],))
        
        vibe_tags = [r[0] for r in cursor.fetchall()]
        
        track = TrackResponse(
            trackId=row[1],
            title=row[5],
            artist=row[6],
            artworkUrl=row[7],
            audioUrl=row[8],
            source=row[9],
            vibeTags=vibe_tags
        )
        
        items.append(HistoryItem(
            feedback_id=row[0],
            track=track,
            action=row[2],
            created_at=row[3],
            undone=bool(row[4])
        ))
    
    # Get total count
    cursor.execute("""
    SELECT COUNT(*) FROM feedback WHERE user_id = ?
    """, (user_id,))
    total = cursor.fetchone()[0]
    
    return HistoryResponse(items=items, total=total)


@app.get("/v1/me", response_model=UserResponse)
async def get_current_user_info(
    user_id: str = Depends(require_user),
    conn: sqlite3.Connection = Depends(get_db)
):
    """Get current user information"""
    cursor = conn.cursor()
    cursor.execute("""
    SELECT user_id, user_type, spotify_user_id, created_at
    FROM users WHERE user_id = ?
    """, (user_id,))
    
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="User not found")
    
    return UserResponse(
        user_id=row[0],
        user_type=row[1],
        spotify_user_id=row[2],
        created_at=row[3]
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
