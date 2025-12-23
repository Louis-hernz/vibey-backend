import httpx
import os
from typing import Optional
import urllib.parse

class YouTubeClient:
    """Client for YouTube Data API to find track videos"""
    
    def __init__(self):
        self.api_key = os.getenv("YOUTUBE_API_KEY", "")
        self.base_url = "https://www.googleapis.com/youtube/v3"
    
    async def search_track(self, title: str, artist: str) -> Optional[dict]:
        """
        Search YouTube for a track and return video info
        
        Returns:
            dict with video_id, title, thumbnail_url
            or None if not found or API key missing
        """
        if not self.api_key:
            return None
        
        # Build search query
        query = f"{title} {artist} official audio"
        
        params = {
            "part": "snippet",
            "q": query,
            "type": "video",
            "maxResults": 1,
            "videoCategoryId": "10",  # Music category
            "key": self.api_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.base_url}/search",
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
                    "youtube_url": f"https://www.youtube.com/watch?v={video_id}",
                    "embed_url": f"https://www.youtube.com/embed/{video_id}",
                    "title": snippet["title"],
                    "thumbnail_url": snippet["thumbnails"]["high"]["url"]
                }
        
        except Exception as e:
            print(f"YouTube search error for {title} - {artist}: {e}")
            return None
