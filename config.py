from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration with tunable parameters"""
    
    # Server config
    app_name: str = "Vibey API"
    debug: bool = True
    
    # Database
    database_url: str = "sqlite:///./vibey.db"
    
    # Spotify OAuth
    spotify_client_id: str = ""
    spotify_client_secret: str = ""
    spotify_redirect_uri: str = "http://localhost:8000/v1/auth/spotify/callback"
    
    # Frontend
    frontend_url: str = "http://localhost:3000"
    
    # Session management
    secret_key: str = "your-secret-key-change-in-production"
    session_cookie_name: str = "vibey_session"
    session_max_age: int = 30 * 24 * 60 * 60  # 30 days
    
    # CORS
    cors_origins: str = "http://127.0.0.1:3000,http://127.0.0.1:5173,http://localhost:3000,http://localhost:5173,https://*.lovable.app,https://*.lovable.dev"
    
    # Recommender parameters (tunable)
    embedding_dim: int = 128
    alpha_like: float = 0.3  # Learning rate for likes
    beta_dislike: float = 0.5  # Learning rate for dislikes
    gamma_more_like: float = 0.6  # Learning rate for more_like_this
    
    # Feed generation
    default_feed_size: int = 10
    explore_candidate_multiplier: int = 5  # Sample N*multiplier candidates, return top N
    vibe_unseen_ratio: float = 0.4  # 40% unseen, 60% liked in vibe mode
    diversity_artist_penalty: float = 0.3  # Penalty for artist frequency
    
    # Initial user preferences
    initial_preference_mode: str = "zero"  # "zero", "random", or "mean"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
