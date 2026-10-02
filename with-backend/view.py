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


def me_to_json(user, following=(), unread_notifications=0, unread_messages=0):
    return {"name": user["name"] if user else None,
            "unread_notifications": unread_notifications,
            "unread_messages": unread_messages,
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


def search_to_json(post_ids, people):
    return {"post_ids": post_ids,
            "people": [{"name": row["name"], "bio": row["bio"], "avatar": upload_url(row["avatar_file"])}
                       for row in people]}


def bookmarks_to_json(post_ids):
    return {"post_ids": post_ids}


def notifications_to_json(rows):
    return [{"id": row["id"], "kind": row["kind"], "actor": row["actor"], "post_id": row["post_id"],
             "created_at": row["created_at"], "read": row["read_at"] is not None} for row in rows]


def sidebar_to_json(trends, suggestions):
    return {"trends": [{"tag": row["tag"], "posts": row["posts"]} for row in trends],
            "suggestions": [{"name": row["name"], "bio": row["bio"], "avatar": upload_url(row["avatar_file"]),
                             "followers": row["followers"]} for row in suggestions]}


def message_to_json(row):
    return {"id": row["id"], "from_me": row["from_me"] == 1, "text": row["text"],
            "sent_at": row["sent_at"], "read": row["read_at"] is not None}


def conversations_to_json(rows):
    return [{"name": row["name"], "avatar": upload_url(row["avatar_file"]), "text": row["text"],
             "sent_at": row["sent_at"], "from_me": row["from_me"] == 1, "unread": row["unread"]}
            for row in rows]


def conversation_to_json(person, rows):
    return {"with": person["name"], "messages": [message_to_json(row) for row in rows]}
