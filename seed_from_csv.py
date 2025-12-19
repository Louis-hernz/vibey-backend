import sqlite3
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Dict, List
from database import Database, vector_to_json
from config import settings


def audio_features_to_embedding(row: pd.Series) -> np.ndarray:
    """
    Convert Spotify audio features from CSV to embedding vector
    """
    # Extract the 9 core audio features
    feature_vector = [
        row['acousticness'],
        row['danceability'],
        row['energy'],
        row['instrumentalness'],
        row['liveness'],
        (row['loudness'] + 60) / 60,  # Normalize loudness (-60 to 0 dB)
        row['speechiness'],
        row['valence'],
        min(row['tempo'] / 200, 1.0),  # Normalize tempo (0-200 BPM)
    ]
    
    # Pad or project to embedding_dim
    if settings.embedding_dim == 9:
        embedding = np.array(feature_vector)
    elif settings.embedding_dim < 9:
        embedding = np.array(feature_vector[:settings.embedding_dim])
    else:
        # Expand to higher dimension using random projection
        # Use track_id as seed for deterministic projection
        seed = hash(row['track_id']) % (2**32)
        np.random.seed(seed)
        projection = np.random.randn(9, settings.embedding_dim)
        embedding = np.dot(np.array(feature_vector), projection)
    
    # Normalize to unit length
    norm = np.linalg.norm(embedding)
    if norm > 0:
        embedding = embedding / norm
    
    return embedding


def assign_vibes(row: pd.Series) -> List[int]:
    """
    Assign vibe tags based on audio features
    Returns list of vibe_ids (1=energetic, 2=chill, 3=melancholic, 4=upbeat, 5=focus, 6=party)
    """
    vibes = []
    
    energy = row['energy']
    valence = row['valence']
    danceability = row['danceability']
    acousticness = row['acousticness']
    instrumentalness = row['instrumentalness']
    
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


def seed_from_csv(csv_path: str, limit: int = 1000):
    """
    Seed database with tracks from Kaggle CSV
    """
    print(f"Reading CSV from {csv_path}...")
    
    # Read CSV
    df = pd.read_csv(csv_path)
    
    print(f"Found {len(df)} tracks in dataset")
    
    # Sample if needed
    if limit and limit < len(df):
        print(f"Sampling {limit} tracks...")
        df = df.sample(n=limit, random_state=42)
    
    print(f"Processing {len(df)} tracks...")
    
    # Connect to database
    db = Database()
    conn = db.connect()
    cursor = conn.cursor()
    timestamp = int(datetime.now().timestamp())
    
    inserted_count = 0
    skipped_count = 0
    
    for idx, row in df.iterrows():
        try:
            # Check for required fields
            if pd.isna(row['track_id']) or pd.isna(row['track_name']) or pd.isna(row['artists']):
                skipped_count += 1
                continue
            
            # Check for required audio features
            required_features = ['acousticness', 'danceability', 'energy', 'instrumentalness',
                               'liveness', 'loudness', 'speechiness', 'valence', 'tempo']
            if any(pd.isna(row[f]) for f in required_features):
                skipped_count += 1
                continue
            
            track_id = str(row['track_id'])
            title = str(row['track_name'])[:200]  # Limit length
            artist = str(row['artists'])[:200]
            album = str(row.get('album_name', ''))[:200] if pd.notna(row.get('album_name')) else ''
            duration_ms = int(row['duration_ms']) if pd.notna(row.get('duration_ms')) else 180000
            
            # Generate embedding from audio features
            embedding = audio_features_to_embedding(row)
            
            # Insert track
            cursor.execute("""
            INSERT OR IGNORE INTO tracks 
            (track_id, title, artist, album, artwork_url, audio_url, preview_url, 
             source, spotify_uri, embedding_vector, duration_ms, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                track_id, title, artist, album,
                "https://via.placeholder.com/300",  # Placeholder artwork
                None,  # No preview URL in dataset
                None,
                'spotify', f'spotify:track:{track_id}',
                vector_to_json(embedding), duration_ms, timestamp
            ))
            
            # Only process vibes if track was inserted (not duplicate)
            if cursor.rowcount > 0:
                # Insert audio features
                cursor.execute("""
                INSERT OR IGNORE INTO audio_features
                (track_id, acousticness, danceability, energy, instrumentalness,
                 liveness, loudness, speechiness, valence, tempo, key, mode,
                 time_signature, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    track_id,
                    float(row['acousticness']),
                    float(row['danceability']),
                    float(row['energy']),
                    float(row['instrumentalness']),
                    float(row['liveness']),
                    float(row['loudness']),
                    float(row['speechiness']),
                    float(row['valence']),
                    float(row['tempo']),
                    int(row['key']) if pd.notna(row.get('key')) else None,
                    int(row['mode']) if pd.notna(row.get('mode')) else None,
                    int(row['time_signature']) if pd.notna(row.get('time_signature')) else None,
                    timestamp
                ))
                
                # Assign vibes
                vibe_ids = assign_vibes(row)
                for vibe_id in vibe_ids:
                    cursor.execute("""
                    INSERT OR IGNORE INTO track_vibes (track_id, vibe_id)
                    VALUES (?, ?)
                    """, (track_id, vibe_id))
                
                inserted_count += 1
                
                if inserted_count % 100 == 0:
                    conn.commit()
                    print(f"Inserted {inserted_count} tracks...")
        
        except Exception as e:
            print(f"Error inserting track {row.get('track_name', 'unknown')}: {e}")
            skipped_count += 1
            continue
    
    conn.commit()
    db.close()
    
    print(f"\n✅ Successfully seeded {inserted_count} tracks!")
    print(f"⚠️  Skipped {skipped_count} tracks (missing data or duplicates)")
    
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
    
    # Print genre distribution (top 10)
    print("\nTop 10 genres:")
    cursor.execute("""
    SELECT track_genre, COUNT(*) as count
    FROM (
        SELECT track_id, '' as track_genre FROM tracks LIMIT 0
    )
    GROUP BY track_genre
    ORDER BY count DESC
    LIMIT 10
    """)
    
    db.close()


if __name__ == "__main__":
    import sys
    import os
    
    # Default to dataset.csv in current directory
    csv_path = "dataset.csv"
    limit = None
    
    # Parse arguments
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    if len(sys.argv) > 2:
        limit = int(sys.argv[2])
    
    # Check if file exists
    if not os.path.exists(csv_path):
        print(f"Error: CSV file not found at {csv_path}")
        print("\nUsage:")
        print("  python seed_from_csv.py [path/to/dataset.csv] [limit]")
        print("\nExamples:")
        print("  python seed_from_csv.py dataset.csv 1000")
        print("  python seed_from_csv.py dataset.csv")
        sys.exit(1)
    
    seed_from_csv(csv_path, limit)
