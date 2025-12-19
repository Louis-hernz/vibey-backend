import sqlite3
import numpy as np
from datetime import datetime
from typing import Dict, List
import time
from database import Database, vector_to_json
from spotify_client import spotify_client
from config import settings


def audio_features_to_embedding(features: Dict) -> np.ndarray:
    """
    Convert Spotify audio features to embedding vector
    Uses 9 normalized features as base embedding
    """
    if not features:
        # Return random embedding if features unavailable
        return np.random.randn(settings.embedding_dim)
    
    # Extract relevant features (already 0-1 normalized except loudness and tempo)
    feature_vector = [
        features.get('acousticness', 0.5),
        features.get('danceability', 0.5),
        features.get('energy', 0.5),
        features.get('instrumentalness', 0.5),
        features.get('liveness', 0.5),
        (features.get('loudness', -30) + 60) / 60,  # Normalize loudness (-60 to 0 dB)
        features.get('speechiness', 0.5),
        features.get('valence', 0.5),
        min(features.get('tempo', 120) / 200, 1.0),  # Normalize tempo (0-200 BPM)
    ]
    
    # Pad or project to embedding_dim
    if settings.embedding_dim == 9:
        embedding = np.array(feature_vector)
    elif settings.embedding_dim < 9:
        embedding = np.array(feature_vector[:settings.embedding_dim])
    else:
        # Expand to higher dimension using random projection
        base = np.array(feature_vector)
        # Create a stable random projection matrix based on features
        seed = int(sum(feature_vector) * 1000)
        np.random.seed(seed)
        projection = np.random.randn(9, settings.embedding_dim)
        embedding = np.dot(base, projection)
    
    # Normalize to unit length
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    return embedding


def assign_vibes(features: Dict) -> List[int]:
    """
    Assign vibe tags based on audio features
    Returns list of vibe_ids
    """
    if not features:
        return [1]  # Default to "energetic"
    
    vibes = []
    
    energy = features.get('energy', 0.5)
    valence = features.get('valence', 0.5)
    danceability = features.get('danceability', 0.5)
    acousticness = features.get('acousticness', 0.5)
    instrumentalness = features.get('instrumentalness', 0.5)
    
    # Energetic: high energy, high danceability
    if energy > 0.7 and danceability > 0.6:
        vibes.append(1)
    
    # Chill: low energy, high acousticness
    if energy < 0.5 and acousticness > 0.5:
        vibes.append(2)
    
    # Melancholic: low valence, low energy
    if valence < 0.4 and energy < 0.5:
        vibes.append(3)
    
    # Upbeat: high valence, moderate-high energy
    if valence > 0.6 and energy > 0.5:
        vibes.append(4)
    
    # Focus: high instrumentalness, moderate energy
    if instrumentalness > 0.5 and 0.3 < energy < 0.7:
        vibes.append(5)
    
    # Party: high danceability, high energy, high valence
    if danceability > 0.7 and energy > 0.6 and valence > 0.6:
        vibes.append(6)
    
    # Ensure at least one vibe
    if not vibes:
        # Assign based on dominant feature
        if energy > 0.6:
            vibes.append(1)  # energetic
        elif valence > 0.6:
            vibes.append(4)  # upbeat
        else:
            vibes.append(2)  # chill
    
    return vibes


def seed_tracks(limit: int = 500):
    """
    Seed database with tracks from Spotify
    """
    print(f"Fetching {limit} tracks from Spotify...")
    
    # Fetch tracks from popular playlists
    tracks = spotify_client.get_top_tracks_from_playlists(limit)
    
    if not tracks:
        print("Error: No tracks fetched. Check Spotify credentials.")
        return
    
    print(f"Fetched {len(tracks)} tracks. Getting audio features...")
    
    # Get audio features
    track_ids = [track['id'] for track in tracks]
    audio_features = spotify_client.get_audio_features(track_ids)
    
    # Create features map
    features_map = {}
    for features in audio_features:
        if features:
            features_map[features['id']] = features
    
    print(f"Got audio features for {len(features_map)} tracks. Inserting into database...")
    
    # Connect to database
    db = Database()
    conn = db.connect()
    cursor = conn.cursor()
    timestamp = int(datetime.now().timestamp())
    
    inserted_count = 0
    
    for track in tracks:
        try:
            track_id = track['id']
            title = track['name']
            artist = ', '.join([artist['name'] for artist in track['artists']])
            album = track['album']['name']
            artwork_url = track['album']['images'][0]['url'] if track['album']['images'] else None
            preview_url = track.get('preview_url')
            spotify_uri = track['uri']
            duration_ms = track.get('duration_ms')
            
            # Get audio features for this track
            features = features_map.get(track_id)
            
            # Generate embedding
            embedding = audio_features_to_embedding(features)
            
            # Insert track
            cursor.execute("""
            INSERT OR IGNORE INTO tracks 
            (track_id, title, artist, album, artwork_url, audio_url, preview_url, 
             source, spotify_uri, embedding_vector, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id, title, artist, album, artwork_url, preview_url, preview_url,
                'spotify', spotify_uri, vector_to_json(embedding), duration_ms, timestamp
            ))
            
            # Insert audio features
            if features:
                cursor.execute("""
                INSERT OR IGNORE INTO audio_features
                (track_id, acousticness, danceability, energy, instrumentalness,
                 liveness, loudness, speechiness, valence, tempo, key, mode,
                 time_signature, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track_id,
                    features.get('acousticness'),
                    features.get('danceability'),
                    features.get('energy'),
                    features.get('instrumentalness'),
                    features.get('liveness'),
                    features.get('loudness'),
                    features.get('speechiness'),
                    features.get('valence'),
                    features.get('tempo'),
                    features.get('key'),
                    features.get('mode'),
                    features.get('time_signature'),
                    timestamp
                ))
            
            # Assign vibes
            vibe_ids = assign_vibes(features)
            for vibe_id in vibe_ids:
                cursor.execute("""
                INSERT OR IGNORE INTO track_vibes (track_id, vibe_id)
                VALUES (?, ?)
                """, (track_id, vibe_id))
            
            inserted_count += 1
            
            if inserted_count % 50 == 0:
                conn.commit()
                print(f"Inserted {inserted_count} tracks...")
        
        except Exception as e:
            print(f"Error inserting track {track.get('name', 'unknown')}: {e}")
            continue
    
    conn.commit()
    db.close()
    
    print(f"Successfully seeded {inserted_count} tracks!")
    
    # Print vibe distribution
    conn = db.connect()
    cursor = conn.cursor()
    cursor.execute("""
    SELECT v.name, COUNT(tv.track_id) as count
    FROM vibes v
    LEFT JOIN track_vibes tv ON v.vibe_id = tv.vibe_id
    GROUP BY v.vibe_id
    ORDER BY count DESC
    """)
    
    print("\nVibe distribution:")
    for row in cursor.fetchall():
        print(f"  {row[0]}: {row[1]} tracks")
    
    db.close()


if __name__ == "__main__":
    import sys
    
    # Check if Spotify credentials are set
    if not settings.spotify_client_id or not settings.spotify_client_secret:
        print("Error: Spotify credentials not set!")
        print("Please set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in .env file")
        sys.exit(1)
    
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 500
    seed_tracks(limit)
