"""
Challenge system for user competitions.
"""

import json
import asyncio
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime, timedelta

CHALLENGES_FILE = Path("data/challenges.json")
_lock = asyncio.Lock()


def _load() -> dict:
    """Load challenges data."""
    if not CHALLENGES_FILE.exists():
        CHALLENGES_FILE.parent.mkdir(parents=True, exist_ok=True)
        return {}
    try:
        return json.loads(CHALLENGES_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save(data: dict) -> None:
    """Save challenges data."""
    CHALLENGES_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


async def create_challenge(chat_id: int, creator_id: int, theme: str, duration_hours: int = 24) -> dict:
    """Create new challenge."""
    async with _lock:
        data = _load()
        chat_key = str(chat_id)
        
        if chat_key not in data:
            data[chat_key] = {"challenges": [], "active": None}
        
        challenge = {
            "id": len(data[chat_key]["challenges"]) + 1,
            "creator_id": creator_id,
            "theme": theme,
            "created_at": datetime.now().isoformat(),
            "duration_hours": duration_hours,
            "expires_at": (datetime.now() + timedelta(hours=duration_hours)).isoformat(),
            "participants": {},
            "votes": {},
            "status": "active"
        }
        
        data[chat_key]["challenges"].append(challenge)
        data[chat_key]["active"] = challenge["id"]
        
        _save(data)
        return challenge


async def join_challenge(chat_id: int, challenge_id: int, user_id: int, demotivator: dict) -> bool:
    """Join challenge with demotivator."""
    async with _lock:
        data = _load()
        chat_key = str(chat_id)
        
        if chat_key not in data:
            return False
        
        # Find challenge
        challenge = None
        for ch in data[chat_key]["challenges"]:
            if ch["id"] == challenge_id and ch["status"] == "active":
                challenge = ch
                break
        
        if not challenge:
            return False
        
        # Check if expired
        if datetime.now() > datetime.fromisoformat(challenge["expires_at"]):
            challenge["status"] = "expired"
            _save(data)
            return False
        
        # Add participant
        challenge["participants"][str(user_id)] = demotivator
        _save(data)
        return True


async def vote_for_demotivator(chat_id: int, challenge_id: int, voter_id: int, creator_id: int) -> bool:
    """Vote for demotivator in challenge."""
    async with _lock:
        data = _load()
        chat_key = str(chat_id)
        
        if chat_key not in data:
            return False
        
        # Find challenge
        challenge = None
        for ch in data[chat_key]["challenges"]:
            if ch["id"] == challenge_id:
                challenge = ch
                break
        
        if not challenge or challenge["status"] != "voting":
            return False
        
        # Check if expired
        if datetime.now() > datetime.fromisoformat(challenge["expires_at"]):
            challenge["status"] = "expired"
            _save(data)
            return False
        
        # Add vote
        vote_key = f"{voter_id}"
        challenge["votes"][vote_key] = creator_id
        _save(data)
        return True


async def get_active_challenge(chat_id: int) -> Optional[dict]:
    """Get active challenge for chat."""
    data = _load()
    chat_key = str(chat_id)
    
    if chat_key not in data:
        return None
    
    active_id = data[chat_key].get("active")
    if not active_id:
        return None
    
    for challenge in data[chat_key]["challenges"]:
        if challenge["id"] == active_id:
            # Check if expired
            if datetime.now() > datetime.fromisoformat(challenge["expires_at"]):
                challenge["status"] = "expired"
                data[chat_key]["active"] = None
                _save(data)
                return None
            return challenge
    
    return None


async def get_challenge_results(chat_id: int, challenge_id: int) -> Optional[dict]:
    """Get challenge results."""
    data = _load()
    chat_key = str(chat_id)
    
    if chat_key not in data:
        return None
    
    for challenge in data[chat_key]["challenges"]:
        if challenge["id"] == challenge_id:
            # Count votes
            vote_counts = {}
            for voter, creator_id in challenge["votes"].items():
                vote_counts[creator_id] = vote_counts.get(creator_id, 0) + 1
            
            # Sort participants by votes
            participants_with_votes = []
            for user_id, demotivator in challenge["participants"].items():
                votes = vote_counts.get(int(user_id), 0)
                participants_with_votes.append({
                    "user_id": int(user_id),
                    "demotivator": demotivator,
                    "votes": votes
                })
            
            participants_with_votes.sort(key=lambda x: x["votes"], reverse=True)
            
            return {
                "challenge": challenge,
                "results": participants_with_votes
            }
    
    return None


async def end_challenge(chat_id: int, challenge_id: int) -> bool:
    """End challenge and calculate results."""
    async with _lock:
        data = _load()
        chat_key = str(chat_id)
        
        if chat_key not in data:
            return False
        
        for challenge in data[chat_key]["challenges"]:
            if challenge["id"] == challenge_id:
                challenge["status"] = "ended"
                if data[chat_key]["active"] == challenge_id:
                    data[chat_key]["active"] = None
                _save(data)
                return True
        
        return False
