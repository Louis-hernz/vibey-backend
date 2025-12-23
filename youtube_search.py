from fastapi import APIRouter, HTTPException
from typing import Optional
import httpx
import os
from pydantic import BaseModel

class YouTubeSearchResponse(BaseModel):
    video_id: str
    embed_url: str
    watch_url: str
    title: str
    thumbnail_url: str

async def search_youtube_track(title: str, artist: str) -> Optional[dict]:
    """
    Search YouTube for a track and return embed-ready data
    
    Args:
        title: Track title
        artist: Artist name
    
    Returns:
        dict with video_id, embed_url, watch_url, title, thumbnail_url
        or None if not found
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    
    if not api_key:
        # Fallback: construct search URL without API
        query = f"{title} {artist} official audio".replace(" ", "+")
        return {
            "video_id": None,
            "embed_url": None,
            "watch_url": f"https://www.youtube.com/results?search_query={query}",
            "title": f"{title} - {artist}",
            "thumbnail_url": None,
            "requires_manual_search": True
        }
    
    # Search YouTube with API
    query = f"{title} {artist} official audio"
    
    params = {
        "part": "snippet",
        "q": query,
        "type": "video",
        "maxResults": 1,
        "videoCategoryId": "10",  # Music category
        "key": api_key
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params=params,
                timeout=10.0
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("items"):
                return None
            
            video = data["items"][0]
            video_id = video["id"]["videoId"]
            snippet = video["snippet"]
            
            return {
                "video_id": video_id,
                "embed_url": f"https://www.youtube.com/embed/{video_id}?autoplay=1",
                "watch_url": f"https://www.youtube.com/watch?v={video_id}",
                "title": snippet["title"],
                "thumbnail_url": snippet["thumbnails"]["high"]["url"],
                "requires_manual_search": False
            }
    
    except Exception as e:
        print(f"YouTube search error for {title} - {artist}: {e}")
        # Fallback
        query = f"{title} {artist} official audio".replace(" ", "+")
        return {
            "video_id": None,
            "embed_url": None,
            "watch_url": f"https://www.youtube.com/results?search_query={query}",
            "title": f"{title} - {artist}",
            "thumbnail_url": None,
            "requires_manual_search": True,
            "error": str(e)
        }
