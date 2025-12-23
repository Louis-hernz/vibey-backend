import asyncio
import httpx
import sqlite3
from config import settings

async def update_batch(offset: int = 0, limit: int = 100):
    """Update a batch of preview URLs"""
    
    # Get Spotify access token
    auth_url = "https://accounts.spotify.com/api/token"
    auth_data = {
        "grant_type": "client_credentials",
        "client_id": settings.spotify_client_id,
        "client_secret": settings.spotify_client_secret
    }
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            auth_response = await client.post(auth_url, data=auth_data)
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
        except Exception as e:
            print(f"Failed to get Spotify token: {e}")
            return 0, 0
        
        headers = {"Authorization": f"Bearer {access_token}"}
        
        # Connect to database
        conn = sqlite3.connect("vibey.db")
        cursor = conn.cursor()
        
        # Get tracks without preview URLs
        cursor.execute("""
        SELECT track_id, title, artist FROM tracks 
        WHERE (preview_url IS NULL OR preview_url = '') 
        AND track_id IS NOT NULL
        LIMIT ? OFFSET ?
        """, (limit, offset))
        
        tracks = cursor.fetchall()
        
        if not tracks:
            conn.close()
            return 0, 0
        
        updated_count = 0
        failed_count = 0
        
        print(f"Processing batch {offset}-{offset+limit}: {len(tracks)} tracks")
        
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
                else:
                    failed_count += 1
                
                await asyncio.sleep(0.35)
                
            except Exception as e:
                failed_count += 1
                continue
        
        conn.commit()
        conn.close()
        
        print(f"Batch complete: Updated {updated_count}, Failed {failed_count}")
        return updated_count, failed_count


async def update_all_previews():
    """Update all tracks in batches"""
    print("Starting preview URL update...")
    
    total_updated = 0
    total_failed = 0
    batch_size = 100
    offset = 0
    
    # Update in batches of 100
    for i in range(10):  # 10 batches = 1000 tracks
        updated, failed = await update_batch(offset=offset, limit=batch_size)
        
        if updated == 0 and failed == 0:
            print("No more tracks to update")
            break
        
        total_updated += updated
        total_failed += failed
        offset += batch_size
        
        # Small delay between batches
        await asyncio.sleep(1)
    
    print(f"\n✅ Preview update complete!")
    print(f"   Updated: {total_updated}")
    print(f"   Failed: {total_failed}")


if __name__ == "__main__":
    asyncio.run(update_all_previews())
