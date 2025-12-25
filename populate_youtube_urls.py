import sqlite3
import asyncio
from youtube_search import search_youtube_track
import time

async def populate_youtube_urls(limit=50):
    """
    Populate YouTube URLs for tracks without Spotify previews
    Runs once to cache YouTube data, then only searches for new tracks
    """
    
    conn = sqlite3.connect("vibey.db")
    cursor = conn.cursor()
    
    # Get tracks without previews AND without cached YouTube URLs
    cursor.execute("""
    SELECT track_id, title, artist 
    FROM tracks 
    WHERE (preview_url IS NULL OR preview_url = '')
    AND (youtube_video_id IS NULL OR youtube_video_id = '')
    LIMIT ?
    """, (limit,))
    
    tracks = cursor.fetchall()
    print(f"Found {len(tracks)} tracks needing YouTube URLs")
    
    if not tracks:
        print("✅ All tracks already have YouTube URLs or Spotify previews!")
        conn.close()
        return
    
    updated = 0
    failed = 0
    
    for i, (track_id, title, artist) in enumerate(tracks, 1):
        try:
            print(f"[{i}/{len(tracks)}] Searching: {title} - {artist}")
            
            youtube_data = await search_youtube_track(title, artist)
            
            if youtube_data and youtube_data.get("video_id"):
                cursor.execute("""
                UPDATE tracks
                SET youtube_video_id = ?,
                    youtube_url = ?,
                    youtube_embed_url = ?
                WHERE track_id = ?
                """, (youtube_data["video_id"], 
                      youtube_data["watch_url"],
                      youtube_data["embed_url"],
                      track_id))
                
                updated += 1
                if updated % 10 == 0:
                    conn.commit()
                    print(f"  ✅ Committed {updated} updates")
            else:
                failed += 1
                print(f"  ⚠️  No YouTube video found")
            
            # Rate limiting - be nice to YouTube API
            await asyncio.sleep(0.5)  # 2 requests per second
            
        except Exception as e:
            print(f"  ❌ Error: {e}")
            failed += 1
            # If we hit quota, stop
            if "403" in str(e) or "Forbidden" in str(e):
                print("\n⚠️  YouTube API quota exceeded! Stopping.")
                break
    
    conn.commit()
    conn.close()
    
    print(f"\n{'='*60}")
    print(f"✅ Updated {updated} tracks")
    print(f"❌ Failed {failed} tracks")
    print(f"{'='*60}")
    print(f"\n💡 Next run will only search for tracks without cached URLs")


if __name__ == "__main__":
    print("🎵 YouTube URL Population Script")
    print("="*60)
    print("This script caches YouTube URLs for tracks without Spotify previews")
    print("Run it daily to populate new tracks (uses ~50-100 API quota)")
    print("="*60)
    print()
    
    # Run with limit of 50 tracks per execution
    asyncio.run(populate_youtube_urls(limit=50))
