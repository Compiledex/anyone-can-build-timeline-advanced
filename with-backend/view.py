"""Timeline: the VIEW. Turns database rows into the JSON the page reads.

The view does not decide anything: it only chooses which fields to send, and their names.
"""

def upload_url(file_name):
    """The address of an uploaded picture, or None when there is none."""
    return "/uploads/" + file_name if file_name else None


def upload_to_json(row):
    return {"id": row["id"], "url": upload_url(row["file_name"])}


def people_to_json(rows):
    return [{"name": row["name"], "avatar": upload_url(row["avatar_file"])} for row in rows]


def me_to_json(user, following=()):
    return {"name": user["name"] if user else None,
            "bio": user["bio"] if user else "",
            "avatar": upload_url(user["avatar_file"]) if user else None,
            "following": [row["name"] for row in following]}


def profile_to_json(row):
    return {"name": row["name"], "bio": row["bio"], "avatar": upload_url(row["avatar_file"]),
            "joined_at": row["joined_at"], "posts": row["posts"],
            "followers": row["followers"], "following": row["following"],
            "you_follow": row["you_follow"] == 1}


def post_to_json(row):
    return {"id": row["id"], "author": row["author"],
            "text": row["text"], "posted_at": row["posted_at"],
            "reply_to": row["reply_to"], "edited_at": row["edited_at"],
            "deleted_at": row["deleted_at"], "picture": upload_url(row["picture_file"]),
            "repost_of": row["repost_of"], "quote_of": row["quote_of"]}


def posts_to_json(rows):
    return [post_to_json(row) for row in rows]


def like_count_to_json(row):
    return {"post_id": row["post_id"], "likes": row["likes"],
            "you_liked": row["you_liked"] == 1}


def like_counts_to_json(rows):
    return [like_count_to_json(row) for row in rows]


def post_to_log_line(row):
    """One line for the terminal: when the post was written, who wrote it, and what it says."""
    return f"{row['posted_at']}  {row['author']}: {row['text']}"
