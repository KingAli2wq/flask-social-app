from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

AchievementDefinition = Dict[str, Any]
AchievementProgress = Dict[str, Any]

ACHIEVEMENTS: List[AchievementDefinition] = [
    {
        "id": "followers_10",
        "name": "Rising Star",
        "description": "Reach 10 followers.",
        "metric": "followers",
        "target": 10,
    },
    {
        "id": "followers_100",
        "name": "Community Builder",
        "description": "Reach 100 followers.",
        "metric": "followers",
        "target": 100,
    },
    {
        "id": "followers_500",
        "name": "Trendsetter",
        "description": "Reach 500 followers.",
        "metric": "followers",
        "target": 500,
    },
    {
        "id": "likes_50",
        "name": "Audience Favorite",
        "description": "Collect 50 total likes across posts and replies.",
        "metric": "likes",
        "target": 50,
    },
    {
        "id": "likes_250",
        "name": "Fan Favorite",
        "description": "Collect 250 total likes across posts and replies.",
        "metric": "likes",
        "target": 250,
    },
    {
        "id": "posts_10",
        "name": "Consistent Voice",
        "description": "Publish 10 posts.",
        "metric": "posts",
        "target": 10,
    },
    {
        "id": "posts_50",
        "name": "Storyteller",
        "description": "Publish 50 posts.",
        "metric": "posts",
        "target": 50,
    },
    {
        "id": "posts_200",
        "name": "Content Powerhouse",
        "description": "Publish 200 posts.",
        "metric": "posts",
        "target": 200,
    },
]

ACHIEVEMENT_INDEX: Dict[str, AchievementDefinition] = {item["id"]: item for item in ACHIEVEMENTS}


def _compute_metrics(
    username: Optional[str],
    *,
    users: Dict[str, Dict[str, Any]],
    posts: List[Dict[str, Any]],
    like_counter: Optional[Callable[[str], int]] = None,
) -> Dict[str, int]:
    if not username:
        return {"followers": 0, "likes": 0, "posts": 0}

    record = users.get(username, {})
    followers = len(record.get("followers", [])) if isinstance(record.get("followers"), list) else 0
    posts_count = sum(1 for post in posts if isinstance(post, dict) and post.get("author") == username)

    if like_counter is not None:
        try:
            likes_total = like_counter(username)
        except Exception:
            likes_total = 0
    else:
        likes_total = 0
        for post in posts:
            if not isinstance(post, dict):
                continue
            if post.get("author") == username:
                likes_total += len(post.get("liked_by", []))
            for reply in post.get("replies", []):
                if isinstance(reply, dict) and reply.get("author") == username:
                    likes_total += len(reply.get("liked_by", []))

    return {
        "followers": followers,
        "likes": likes_total,
        "posts": posts_count,
    }


def compute_achievement_progress(
    username: Optional[str],
    *,
    users: Dict[str, Dict[str, Any]],
    posts: List[Dict[str, Any]],
    like_counter: Optional[Callable[[str], int]] = None,
) -> List[AchievementProgress]:
    metrics = _compute_metrics(username, users=users, posts=posts, like_counter=like_counter)
    progress: List[AchievementProgress] = []
    for definition in ACHIEVEMENTS:
        target = max(0, int(definition.get("target", 0)))
        current = int(metrics.get(definition.get("metric", ""), 0))
        percent = 100 if target == 0 else min(100, int((current / target) * 100))
        remaining = max(0, target - current)
        progress.append(
            {
                "id": definition["id"],
                "name": definition["name"],
                "description": definition["description"],
                "metric": definition.get("metric"),
                "target": target,
                "current": current,
                "percent": percent,
                "complete": current >= target,
                "remaining": remaining,
            }
        )
    return progress
