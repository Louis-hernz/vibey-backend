import sqlite3
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from config import settings
from database import Database
import time

def update_preview_urls():
    """Fetch preview URLs from Spotify API for tracks that don't have them"""
    
    # Initialize Spotify client
    try:
        auth_manager = SpotifyClientCredentials(
            client_id=settings.spotify_client_id,
            client_secret=settings.spotify_client_secret
        )
        sp = spotipy.Spotify(auth_manager=auth_manager)
    except Exception as e:
        print(f"Failed to initialize Spotify client: {e}")
        return
    
    # Connect to database
    db = Database()
    conn = db.connect()
    cursor = conn.cursor()
    
    # Get all tracks without preview URLs
    cursor.execute("""
    SELECT track_id, title, artist FROM tracks 
    WHERE (preview_url IS NULL OR preview_url = '') 
    AND spotify_uri IS NOT NULL
    LIMIT 100
    """)
    
    tracks = cursor.fetchall()
    print(f"Found {len(tracks)} tracks without preview URLs")
    
    updated_count = 0
    failed_count = 0
    
    for track_id, title, artist in tracks:
        try:
            # Fetch track info from Spotify
            track_info = sp.track(track_id)
            
            preview_url = track_info.get('preview_url')
            album_art = None
            
            # Get album artwork
            if track_info.get('album') and track_info['album'].get('images'):
                images = track_info['album']['images']
                if images:
                    album_art = images[0]['url']  # Highest resolution
            
            # Update database
            if preview_url or album_art:
                cursor.execute("""
                UPDATE tracks 
                SET preview_url = ?, 
                    audio_url = ?,
                    artwork_url = ?
                WHERE track_id = ?
                """, (preview_url, preview_url, album_art or "https://via.placeholder.com/300", track_id))
                
                updated_count += 1
                if updated_count % 10 == 0:
                    conn.commit()
                    print(f"Updated {updated_count} tracks...")
            else:
                failed_count += 1
                print(f"No preview available for: {title} by {artist}")
            
            # Rate limiting - Spotify allows 180 requests per minute
            time.sleep(0.35)  # ~170 requests per minute to be safe
            
        except Exception as e:
            print(f"Error fetching {title} by {artist}: {e}")
            failed_count += 1
            continue
    
    conn.commit()
    db.close()
    
    print(f"\n✅ Successfully updated {updated_count} tracks!")
    print(f"⚠️  Failed to update {failed_count} tracks")
    print(f"\nNote: Run this script multiple times to update all tracks (100 at a time)")


if __name__ == "__main__":
    print("Fetching preview URLs from Spotify API...")
    print("This will take a few minutes due to rate limiting.\n")
    update_preview_urls()
