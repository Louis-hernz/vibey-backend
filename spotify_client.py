import spotipy
from spotipy.oauth2 import SpotifyOAuth, SpotifyClientCredentials
import httpx
from typing import Optional, List, Dict, Any
from config import settings
import time


class SpotifyClient:
    """Spotify API client for OAuth and data fetching"""
    
    def __init__(self):
        self.client_id = settings.spotify_client_id
        self.client_secret = settings.spotify_client_secret
        self.redirect_uri = settings.spotify_redirect_uri
        
        # Client credentials flow for seeding data
        if self.client_id and self.client_secret:
            self.client_creds = SpotifyClientCredentials(
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            self.sp_app = spotipy.Spotify(client_credentials_manager=self.client_creds)
        else:
            self.sp_app = None
    
    def get_oauth_url(self, state: str) -> str:
        """Generate Spotify OAuth authorization URL"""
        scope = "user-read-email user-read-private user-library-read"
        oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri,
            scope=scope,
            state=state,
            show_dialog=True
        )
        return oauth.get_authorize_url()
    
    def exchange_code(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        token_info = oauth.get_access_token(code, as_dict=True)
        return token_info
    
    def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token"""
        oauth = SpotifyOAuth(
            client_id=self.client_id,
            client_secret=self.client_secret,
            redirect_uri=self.redirect_uri
        )
        token_info = oauth.refresh_access_token(refresh_token)
        return token_info
    
    def get_user_profile(self, access_token: str) -> Dict[str, Any]:
        """Get Spotify user profile"""
        sp = spotipy.Spotify(auth=access_token)
        return sp.current_user()
    
    def get_audio_features(self, track_ids: List[str]) -> List[Optional[Dict[str, Any]]]:
        """Get audio features for multiple tracks"""
        if not self.sp_app:
            return [None] * len(track_ids)
        
        # Spotify API supports max 100 tracks per request
        features = []
        for i in range(0, len(track_ids), 100):
            batch = track_ids[i:i+100]
            batch_features = self.sp_app.audio_features(batch)
            features.extend(batch_features)
        
        return features
    
    def search_tracks(self, query: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Search for tracks"""
        if not self.sp_app:
            return []
        
        results = self.sp_app.search(q=query, type='track', limit=limit)
        return results['tracks']['items']
    
    def get_playlist_tracks(self, playlist_id: str) -> List[Dict[str, Any]]:
        """Get tracks from a playlist"""
        if not self.sp_app:
            return []
        
        results = self.sp_app.playlist_tracks(playlist_id)
        tracks = []
        
        # Handle pagination
        while results:
            tracks.extend([item['track'] for item in results['items'] if item['track']])
            if results['next']:
                results = self.sp_app.next(results)
            else:
                results = None
        
        return tracks
    
    def get_top_tracks_from_playlists(self, limit: int = 500) -> List[Dict[str, Any]]:
        """Get popular tracks using search across various genres"""
        if not self.sp_app:
            return []
        
        # Search queries for diverse music
        search_queries = [
            'year:2024',
            'year:2023',
            'genre:pop',
            'genre:rock',
            'genre:hip-hop',
            'genre:electronic',
            'genre:indie',
            'genre:r&b',
            'genre:country',
            'genre:jazz',
            'genre:classical',
            'genre:metal',
        ]
        
        all_tracks = []
        seen_ids = set()
        
        tracks_per_query = limit // len(search_queries) + 10
        
        for query in search_queries:
            if len(all_tracks) >= limit:
                break
            
            try:
                results = self.sp_app.search(q=query, type='track', limit=min(50, tracks_per_query))
                tracks = results['tracks']['items']
                
                for track in tracks:
                    if track and track.get('id') and track['id'] not in seen_ids:
                        all_tracks.append(track)
                        seen_ids.add(track['id'])
                    
                    if len(all_tracks) >= limit:
                        break
                
                time.sleep(0.2)  # Rate limiting
                
            except Exception as e:
                print(f"Error searching '{query}': {e}")
                continue
        
        return all_tracks[:limit]


# Global Spotify client instance
spotify_client = SpotifyClient()
