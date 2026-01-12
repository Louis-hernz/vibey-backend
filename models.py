from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class UserCreate(BaseModel):
    """Request model for creating a guest user"""
    pass


class UserResponse(BaseModel):
    """Response model for user data"""
    user_id: str
    user_type: str  # "guest" or "spotify"
    spotify_user_id: Optional[str] = None
    spotify_display_name: Optional[str] = None
    has_spotify_premium: bool = False
    created_at: int


class VibeResponse(BaseModel):
    """Response model for vibe data"""
    vibe_id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None


class TrackResponse(BaseModel):
    """Response model for track data (exact shape requested)"""
    trackId: str
    title: str
    artist: str
    artworkUrl: Optional[str] = None
    audioUrl: Optional[str] = None  # Spotify 30-second preview
    youtubeUrl: Optional[str] = None  # YouTube video URL  
    youtubeEmbedUrl: Optional[str] = None  # YouTube embed URL for iframe
    spotifyUri: Optional[str] = None  # For Spotify Premium playback (e.g. "spotify:track:xxx")
    source: str = "spotify"
    playbackSource: str = "preview"  # "preview", "youtube", or "spotify_premium"
    duration_ms: Optional[int] = None
    vibeTags: List[str] = []
    previouslyLiked: bool = False  # True if user has liked this track before (enjoy mode)


class FeedRequest(BaseModel):
    """Request model for feed generation"""
    mode: str = Field(..., pattern="^(explore|vibe)$")
    vibe_id: Optional[int] = None
    limit: int = Field(default=10, ge=1, le=50)
    seed: Optional[int] = None


class FeedResponse(BaseModel):
    """Response model for feed"""
    tracks: List[TrackResponse]
    mode: str
    vibe_id: Optional[int] = None


class FeedbackRequest(BaseModel):
    """Request model for feedback"""
    track_id: str
    action: str = Field(..., pattern="^(like|dislike|more_like_this|undo)$")


class FeedbackResponse(BaseModel):
    """Response model for feedback"""
    success: bool
    feedback_id: Optional[int] = None
    message: Optional[str] = None


class HistoryItem(BaseModel):
    """History item model"""
    feedback_id: int
    track: TrackResponse
    action: str
    created_at: int
    undone: bool


class HistoryResponse(BaseModel):
    """Response model for history"""
    items: List[HistoryItem]
    total: int


class ErrorResponse(BaseModel):
    """Error response model"""
    error: str
    detail: Optional[str] = None
