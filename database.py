import sqlite3
import json
import numpy as np
from typing import Optional
from datetime import datetime
from config import settings


class Database:
    """SQLite database manager for Vibey"""
    
    def __init__(self, db_path: str = "vibey.db"):
        self.db_path = db_path
        self.conn = None
    
    def connect(self):
        """Establish database connection"""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        return self.conn
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
    
    def init_db(self):
        """Initialize database schema"""
        conn = self.connect()
        cursor = conn.cursor()
        
        # Users table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            user_type TEXT NOT NULL CHECK(user_type IN ('guest', 'spotify')),
            spotify_user_id TEXT UNIQUE,
            spotify_access_token TEXT,
            spotify_refresh_token TEXT,
            spotify_token_expires_at INTEGER,
            spotify_display_name TEXT,
            spotify_product TEXT,  -- 'premium', 'free', or NULL for guests
            preference_vector TEXT NOT NULL,  -- JSON array
            created_at INTEGER NOT NULL,
            updated_at INTEGER NOT NULL
        )
        """)
        
        # Sessions table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            expires_at INTEGER NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        # Vibes table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS vibes (
            vibe_id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            description TEXT,
            color TEXT,
            created_at INTEGER NOT NULL
        )
        """)
        
        # Tracks table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tracks (
            track_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            artist TEXT NOT NULL,
            album TEXT,
            artwork_url TEXT,
            audio_url TEXT,
            preview_url TEXT,
            youtube_video_id TEXT,  -- Cached YouTube video ID
            youtube_url TEXT,  -- Cached YouTube watch URL  
            youtube_embed_url TEXT,  -- Cached YouTube embed URL
            source TEXT NOT NULL DEFAULT 'spotify',
            spotify_uri TEXT,
            embedding_vector TEXT NOT NULL,  -- JSON array
            duration_ms INTEGER,
            created_at INTEGER NOT NULL
        )
        """)
        
        # Track vibes (many-to-many relationship)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS track_vibes (
            track_id TEXT NOT NULL,
            vibe_id INTEGER NOT NULL,
            confidence REAL DEFAULT 1.0,
            PRIMARY KEY (track_id, vibe_id),
            FOREIGN KEY (track_id) REFERENCES tracks(track_id),
            FOREIGN KEY (vibe_id) REFERENCES vibes(vibe_id)
        )
        """)
        
        # Feedback table
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS feedback (
            feedback_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            action TEXT NOT NULL CHECK(action IN ('like', 'dislike', 'more_like_this', 'skip')),
            preference_delta TEXT,  -- JSON array of the delta applied
            created_at INTEGER NOT NULL,
            undone INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (track_id) REFERENCES tracks(track_id)
        )
        """)
        
        # Seen tracks (for explore mode)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS seen_tracks (
            user_id TEXT NOT NULL,
            track_id TEXT NOT NULL,
            seen_at INTEGER NOT NULL,
            PRIMARY KEY (user_id, track_id),
            FOREIGN KEY (user_id) REFERENCES users(user_id),
            FOREIGN KEY (track_id) REFERENCES tracks(track_id)
        )
        """)
        
        # Spotify audio features cache
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS audio_features (
            track_id TEXT PRIMARY KEY,
            acousticness REAL,
            danceability REAL,
            energy REAL,
            instrumentalness REAL,
            liveness REAL,
            loudness REAL,
            speechiness REAL,
            valence REAL,
            tempo REAL,
            key INTEGER,
            mode INTEGER,
            time_signature INTEGER,
            fetched_at INTEGER NOT NULL,
            FOREIGN KEY (track_id) REFERENCES tracks(track_id)
        )
        """)
        
        # Create indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_spotify ON users(spotify_user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_expires ON sessions(expires_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_user ON feedback(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_track ON feedback(track_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_seen_user ON seen_tracks(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_track_vibes_vibe ON track_vibes(vibe_id)")
        
        conn.commit()
        self.close()
    
    def seed_vibes(self):
        """Seed initial vibe taxonomy"""
        conn = self.connect()
        cursor = conn.cursor()
        
        vibes = [
            ("energetic", "High energy, intense and powerful", "#FF6B6B"),
            ("chill", "Relaxed, calm and mellow", "#4ECDC4"),
            ("melancholic", "Sad, emotional and introspective", "#95A5A6"),
            ("upbeat", "Happy, positive and cheerful", "#FFD93D"),
            ("focus", "Concentration and productivity", "#6C5CE7"),
            ("party", "Dance, celebration and excitement", "#FD79A8"),
        ]
        
        timestamp = int(datetime.now().timestamp())
        
        for name, description, color in vibes:
            cursor.execute("""
            INSERT OR IGNORE INTO vibes (name, description, color, created_at)
            VALUES (?, ?, ?, ?)
            """, (name, description, color, timestamp))
        
        conn.commit()
        self.close()


def vector_to_json(vector: np.ndarray) -> str:
    """Convert numpy array to JSON string"""
    return json.dumps(vector.tolist())


def json_to_vector(json_str: str) -> np.ndarray:
    """Convert JSON string to numpy array"""
    return np.array(json.loads(json_str))


if __name__ == "__main__":
    db = Database()
    print("Initializing database...")
    db.init_db()
    print("Seeding vibes...")
    db.seed_vibes()
    print("Database initialized successfully!")
