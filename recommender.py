import numpy as np
import sqlite3
from typing import List, Dict, Optional, Tuple
from datetime import datetime
import json
import random
from collections import Counter
from config import settings
from database import json_to_vector, vector_to_json


class RecommenderEngine:
    """Music recommendation engine using preference vectors"""
    
    def __init__(self, db_conn: sqlite3.Connection):
        self.conn = db_conn
        self.alpha = settings.alpha_like
        self.beta = settings.beta_dislike
        self.gamma = settings.gamma_more_like
        self.embedding_dim = settings.embedding_dim
    
    def normalize_vector(self, vector: np.ndarray) -> np.ndarray:
        """Normalize vector to unit length"""
        norm = np.linalg.norm(vector)
        if norm == 0:
            return vector
        return vector / norm
    
    def get_user_preference(self, user_id: str) -> np.ndarray:
        """Get user's preference vector"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT preference_vector FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        if row:
            return json_to_vector(row[0])
        return np.zeros(self.embedding_dim)
    
    def update_user_preference(self, user_id: str, new_vector: np.ndarray):
        """Update user's preference vector"""
        cursor = self.conn.cursor()
        timestamp = int(datetime.now().timestamp())
        cursor.execute("""
        UPDATE users 
        SET preference_vector = ?, updated_at = ?
        WHERE user_id = ?
        """, (vector_to_json(new_vector), timestamp, user_id))
        self.conn.commit()
    
    def apply_feedback(self, user_id: str, track_id: str, action: str) -> Tuple[np.ndarray, int]:
        """
        Apply feedback and update user preference vector
        Returns: (preference_delta, feedback_id)
        """
        # Get track embedding
        cursor = self.conn.cursor()
        cursor.execute("SELECT embedding_vector FROM tracks WHERE track_id = ?", (track_id,))
        row = cursor.fetchone()
        if not row:
            raise ValueError(f"Track {track_id} not found")
        
        track_embedding = json_to_vector(row[0])
        
        # Get current preference
        preference = self.get_user_preference(user_id)
        
        # Calculate delta based on action
        if action == "like":
            delta = self.alpha * track_embedding
        elif action == "dislike":
            delta = -self.beta * track_embedding
        elif action == "more_like_this":
            delta = self.gamma * track_embedding
        else:
            delta = np.zeros(self.embedding_dim)
        
        # Update preference
        new_preference = self.normalize_vector(preference + delta)
        self.update_user_preference(user_id, new_preference)
        
        # Log feedback
        timestamp = int(datetime.now().timestamp())
        cursor.execute("""
        INSERT INTO feedback (user_id, track_id, action, preference_delta, created_at)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, track_id, action, vector_to_json(delta), timestamp))
        self.conn.commit()
        
        feedback_id = cursor.lastrowid
        
        return delta, feedback_id
    
    def undo_feedback(self, user_id: str) -> bool:
        """Undo the last feedback action"""
        cursor = self.conn.cursor()
        
        # Get last non-undone feedback
        cursor.execute("""
        SELECT feedback_id, preference_delta
        FROM feedback
        WHERE user_id = ? AND undone = 0
        ORDER BY created_at DESC
        LIMIT 1
        """, (user_id,))
        
        row = cursor.fetchone()
        if not row:
            return False
        
        feedback_id, delta_json = row
        delta = json_to_vector(delta_json)
        
        # Reverse the delta
        preference = self.get_user_preference(user_id)
        new_preference = self.normalize_vector(preference - delta)
        self.update_user_preference(user_id, new_preference)
        
        # Mark as undone
        cursor.execute("""
        UPDATE feedback SET undone = 1 WHERE feedback_id = ?
        """, (feedback_id,))
        self.conn.commit()
        
        return True
    
    def score_tracks(self, user_id: str, track_ids: List[str]) -> Dict[str, float]:
        """Score tracks based on user preference"""
        preference = self.get_user_preference(user_id)
        
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(track_ids))
        cursor.execute(f"""
        SELECT track_id, embedding_vector
        FROM tracks
        WHERE track_id IN ({placeholders})
        """, track_ids)
        
        scores = {}
        for row in cursor.fetchall():
            track_id = row[0]
            embedding = json_to_vector(row[1])
            score = np.dot(preference, embedding)
            scores[track_id] = float(score)
        
        return scores
    
    def get_unseen_tracks(self, user_id: str, vibe_id: Optional[int] = None) -> List[str]:
        """Get tracks the user hasn't seen yet"""
        cursor = self.conn.cursor()
        
        if vibe_id:
            cursor.execute("""
            SELECT t.track_id
            FROM tracks t
            INNER JOIN track_vibes tv ON t.track_id = tv.track_id
            WHERE tv.vibe_id = ?
            AND t.track_id NOT IN (
                SELECT track_id FROM seen_tracks WHERE user_id = ?
            )
            """, (vibe_id, user_id))
        else:
            cursor.execute("""
            SELECT track_id
            FROM tracks
            WHERE track_id NOT IN (
                SELECT track_id FROM seen_tracks WHERE user_id = ?
            )
            """, (user_id,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def get_liked_tracks(self, user_id: str, vibe_id: Optional[int] = None) -> List[str]:
        """Get tracks the user has liked"""
        cursor = self.conn.cursor()
        
        if vibe_id:
            cursor.execute("""
            SELECT DISTINCT f.track_id
            FROM feedback f
            INNER JOIN track_vibes tv ON f.track_id = tv.track_id
            WHERE f.user_id = ? 
            AND f.action IN ('like', 'more_like_this')
            AND f.undone = 0
            AND tv.vibe_id = ?
            """, (user_id, vibe_id))
        else:
            cursor.execute("""
            SELECT DISTINCT track_id
            FROM feedback
            WHERE user_id = ? 
            AND action IN ('like', 'more_like_this')
            AND undone = 0
            """, (user_id,))
        
        return [row[0] for row in cursor.fetchall()]
    
    def apply_diversity_penalty(self, track_ids: List[str], scores: Dict[str, float]) -> Dict[str, float]:
        """Apply penalty to tracks from over-represented artists"""
        cursor = self.conn.cursor()
        placeholders = ','.join('?' * len(track_ids))
        cursor.execute(f"""
        SELECT track_id, artist FROM tracks WHERE track_id IN ({placeholders})
        """, track_ids)
        
        track_artists = {row[0]: row[1] for row in cursor.fetchall()}
        artist_counts = Counter(track_artists.values())
        
        adjusted_scores = {}
        for track_id, score in scores.items():
            artist = track_artists.get(track_id)
            if artist and artist_counts[artist] > 1:
                # Apply penalty proportional to artist frequency
                penalty = settings.diversity_artist_penalty * (artist_counts[artist] - 1)
                adjusted_scores[track_id] = score * (1 - penalty)
            else:
                adjusted_scores[track_id] = score
        
        return adjusted_scores
    
    def generate_explore_feed(self, user_id: str, limit: int, seed: Optional[int] = None) -> List[str]:
        """Generate explore mode feed (only unseen tracks)"""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # Get unseen tracks
        unseen = self.get_unseen_tracks(user_id)
        
        if not unseen:
            return []
        
        # Sample more candidates than needed
        candidate_count = min(len(unseen), limit * settings.explore_candidate_multiplier)
        candidates = random.sample(unseen, candidate_count)
        
        # Score candidates
        scores = self.score_tracks(user_id, candidates)
        
        # Apply diversity penalty
        scores = self.apply_diversity_penalty(candidates, scores)
        
        # Sort by score and return top N
        sorted_tracks = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [track_id for track_id, _ in sorted_tracks[:limit]]
    
    def generate_vibe_feed(self, user_id: str, vibe_id: int, limit: int, seed: Optional[int] = None) -> List[str]:
        """Generate vibe mode feed (mix of liked and unseen within vibe)"""
        if seed is not None:
            random.seed(seed)
            np.random.seed(seed)
        
        # Calculate split
        unseen_count = int(limit * settings.vibe_unseen_ratio)
        liked_count = limit - unseen_count
        
        result = []
        
        # Get liked tracks in this vibe
        liked_tracks = self.get_liked_tracks(user_id, vibe_id)
        if liked_tracks:
            sampled_liked = random.sample(liked_tracks, min(liked_count, len(liked_tracks)))
            result.extend(sampled_liked)
        
        # Get unseen tracks in this vibe, similar to liked tracks
        unseen_tracks = self.get_unseen_tracks(user_id, vibe_id)
        if unseen_tracks:
            # Score unseen tracks
            scores = self.score_tracks(user_id, unseen_tracks)
            scores = self.apply_diversity_penalty(unseen_tracks, scores)
            
            # Sort by similarity to user preference
            sorted_unseen = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            unseen_to_add = min(unseen_count, len(sorted_unseen))
            result.extend([track_id for track_id, _ in sorted_unseen[:unseen_to_add]])
        
        # Shuffle the final feed
        random.shuffle(result)
        
        return result[:limit]
    
    def mark_tracks_seen(self, user_id: str, track_ids: List[str]):
        """Mark tracks as seen by user"""
        cursor = self.conn.cursor()
        timestamp = int(datetime.now().timestamp())
        
        for track_id in track_ids:
            cursor.execute("""
            INSERT OR IGNORE INTO seen_tracks (user_id, track_id, seen_at)
            VALUES (?, ?, ?)
            """, (user_id, track_id, timestamp))
        
        self.conn.commit()
