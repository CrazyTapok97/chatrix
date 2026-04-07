"""
User statistics for likes system.
"""

from utils.likes import _load, _key


def user_stats(chat_id: int, user_id: int) -> dict:
    """Statistics for specific user."""
    data = _load()
    stats = {
        "total_votes": 0,
        "likes_given": 0,
        "dislikes_given": 0,
        "top_voted": [],
    }
    
    for k, entry in data.items():
        mid, cid = k.split(":", 1)
        if int(cid) != chat_id:
            continue
        
        uid = str(user_id)
        if uid in entry.get("voters", {}):
            vote = entry["voters"][uid]
            stats["total_votes"] += 1
            if vote == "up":
                stats["likes_given"] += 1
            else:
                stats["dislikes_given"] += 1
            
            # Add to top voted if user liked it and it has positive score
            if vote == "up":
                score = entry["likes"] - entry["dislikes"]
                if score > 0:
                    stats["top_voted"].append({
                        "title": entry.get("title", ""),
                        "subtitle": entry.get("subtitle", ""),
                        "score": score,
                    })
    
    # Sort top voted by score
    stats["top_voted"].sort(key=lambda x: x["score"], reverse=True)
    stats["top_voted"] = stats["top_voted"][:3]  # Top 3
    
    return stats
