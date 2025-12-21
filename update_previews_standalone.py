import sqlite3
import httpx
import asyncio
import os

async def update_preview_urls():
    """Fetch preview URLs from Spotify API for tracks that don't have them"""
    
    # Get credentials from environment variables
    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    client_secret = os.getenv("SPOTIFY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("❌ Missing SPOTIFY_CLIENT_ID or SPOTIFY_CLIENT_SECRET environment variables")
        return
    
    print(f"Using Spotify Client ID: {client_id[:10]}...")
    
    # Get Spotify access token
    auth_url = "https://accounts.spotify.com/api/token"
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    
    async with httpx.AsyncClient() as client:
        try:
            print("🔐 Getting Spotify access token...")
            auth_response = await client.post(auth_url, data=auth_data)
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            print("✅ Got access token!")
        except Exception as e:
            print(f"❌ Failed to get Spotify access token: {e}")
            return
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Connect to database
        print("📊 Connecting to database...")
        conn = sqlite3.connect("vibey.db")
        cursor = conn.cursor()
        
        # Get all tracks without preview URLs
        cursor.execute("""
        SELECT track_id, title, artist FROM tracks 
        WHERE (preview_url IS NULL OR preview_url = '') 
        AND track_id IS NOT NULL
        LIMIT 100
        """)
        
        tracks = cursor.fetchall()
        print(f"🎵 Found {len(tracks)} tracks without preview URLs\n")
        
        updated_count = 0
        failed_count = 0
        
        for i, (track_id, title, artist) in enumerate(tracks, 1):
            try:
                # Fetch track info from Spotify
                track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
                response = await client.get(track_url, headers=headers)
                
                if response.status_code != 200:
                    print(f"❌ [{i}/{len(tracks)}] API error for {title}: {response.status_code}")
                    failed_count += 1
                    continue
                
                track_info = response.json()
                
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
                    status = "✅" if preview_url else "🖼️ "
                    print(f"{status} [{i}/{len(tracks)}] {title[:40]} - {artist[:30]}")
                    
                    if updated_count % 10 == 0:
                        conn.commit()
                else:
                    failed_count += 1
                    print(f"⚠️  [{i}/{len(tracks)}] No preview: {title[:40]}")
                
                # Rate limiting - Spotify allows 180 requests per minute
                await asyncio.sleep(0.35)  # ~170 requests per minute
                
            except Exception as e:
                print(f"❌ [{i}/{len(tracks)}] Error: {title}: {e}")
                failed_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"✅ Successfully updated {updated_count} tracks!")
        print(f"⚠️  Failed to update {failed_count} tracks")
        print(f"{'='*60}")
        print(f"\n💡 Tip: Run this script ~10 times to update all ~1000 tracks")


if __name__ == "__main__":
    print("="*60)
    print("🎵 Spotify Preview URL Updater")
    print("="*60)
    print()
    asyncio.run(update_preview_urls())
