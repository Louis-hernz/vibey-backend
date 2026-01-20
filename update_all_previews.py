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
    
    print(f"Authenticating with Spotify...")
    print(f"  Client ID: {settings.spotify_client_id}")
    print(f"  Client Secret: {'*' * 20}{settings.spotify_client_secret[-4:] if settings.spotify_client_secret else 'MISSING'}")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            auth_response = await client.post(auth_url, data=auth_data)
            print(f"  Auth Response Status: {auth_response.status_code}")
            
            if auth_response.status_code != 200:
                print(f"  Auth Error: {auth_response.text}")
                return 0, 0
            
            auth_response.raise_for_status()
            access_token = auth_response.json()["access_token"]
            print(f"  ✓ Successfully authenticated! Token: {access_token[:20]}...")
        except Exception as e:
            print(f"  ❌ Failed to get Spotify token: {e}")
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
        
        for i, (track_id, title, artist) in enumerate(tracks):
            try:
                track_url = f"https://api.spotify.com/v1/tracks/{track_id}"
                
                # Detailed logging for first 5 tracks
                if offset == 0 and i < 5:
                    print(f"\n  [Track {i+1}] ID: {track_id}")
                    print(f"  [Track {i+1}] Title: {title}")
                    print(f"  [Track {i+1}] Artist: {artist}")
                    print(f"  [Track {i+1}] URL: {track_url}")
                
                response = await client.get(track_url, headers=headers)
                
                # Detailed logging for first 5 tracks
                if offset == 0 and i < 5:
                    print(f"  [Track {i+1}] Response Status: {response.status_code}")
                    if response.status_code != 200:
                        print(f"  [Track {i+1}] Response Body: {response.text[:200]}")
                
                if response.status_code != 200:
                    print(f"  ❌ Failed {track_id} ({title}): HTTP {response.status_code} - {response.text[:100]}")
                    failed_count += 1
                    continue
                
                track_info = response.json()
                preview_url = track_info.get('preview_url')
                album_art = None
                
                if track_info.get('album') and track_info['album'].get('images'):
                    images = track_info['album']['images']
                    if images:
                        album_art = images[0]['url']
                
                # Detailed logging for first 5 tracks
                if offset == 0 and i < 5:
                    print(f"  [Track {i+1}] Preview URL: {preview_url or 'None'}")
                    print(f"  [Track {i+1}] Artwork URL: {album_art or 'None'}")
                
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
                        print(f"  ✓ Updated {updated_count} tracks...")
                else:
                    failed_count += 1
                    if offset == 0 and i < 5:
                        print(f"  [Track {i+1}] ⚠️  No preview or artwork found")
                
                await asyncio.sleep(0.5)  # Increased from 0.35 to 0.5 seconds
                
            except Exception as e:
                print(f"  ❌ Error for {track_id} ({title}): {str(e)}")
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
        
        # Delay between batches to avoid rate limiting
        if i < 9:  # Don't delay after last batch
            print(f"  ⏸  Waiting 10 seconds before next batch...")
            await asyncio.sleep(10)
    
    print(f"\n✅ Preview update complete!")
    print(f"   Updated: {total_updated}")
    print(f"   Failed: {total_failed}")


if __name__ == "__main__":
    asyncio.run(update_all_previews())
