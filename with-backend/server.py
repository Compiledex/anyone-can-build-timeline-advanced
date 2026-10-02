"""Timeline: the backend. Start it with `python3 server.py`, then open http://localhost:8009

This file has three parts:
  CONTROLLER  reads each request and decides what to do
  MODEL       the rules, and the database (three tables: users, posts and likes)
  VIEW        turns database rows into the JSON answer
It uses only the Python standard library, so there is nothing to install.
"""

import argparse
import json
import os
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "timeline.db")

# The page files this server gives to the browser, and the type of each one.
PAGE_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


# ============================================================================
#  CONTROLLER
#  Reads the request. Picks what to do. Asks the model. Sends the answer.
#
#  POST /posts    a new post, or a reply      PUT /posts     edit a post
#  DELETE /posts  delete a post               GET /posts     new posts
#  POST /likes    like a post                 DELETE /likes  unlike a post
#  GET /likes     every like count            GET /changes   every edited or deleted post
# ============================================================================

class TimelineHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        url = urlparse(self.path)
        query = parse_qs(url.query)
        if url.path == "/posts":
            try:
                after = int(query.get("after", ["0"])[0])
            except ValueError:
                self.send_json(400, {"error": "'after' must be a whole number."})
                return
            rows = posts_after(self.server.db_path, after)
            self.send_json(200, posts_to_json(rows))
        elif url.path == "/likes":
            name = query.get("name", [""])[0]
            self.send_json(200, like_counts_to_json(like_counts(self.server.db_path, name)))
        elif url.path == "/changes":
            self.send_json(200, posts_to_json(changed_posts(self.server.db_path)))
        elif url.path in PAGE_FILES:
            file_name, content_type = PAGE_FILES[url.path]
            try:
                with open(os.path.join(HERE, file_name), "rb") as page_file:
                    self.send_answer(200, content_type, page_file.read())
            except OSError:
                self.send_json(404, {"error": "The file " + file_name + " is missing."})
        else:
            self.send_json(404, {"error": "There is nothing at " + url.path})

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in ("/posts", "/likes"):
            self.send_json(404, {"error": "You can only send a post to /posts, or a like to /likes"})
            return
        data = self.read_json()
        if data is None:
            return
        try:
            if path == "/posts":
                row = save_post(self.server.db_path, data.get("author"), data.get("text"),
                                data.get("reply_to"))
                self.send_json(201, post_to_json(row))
                print(post_to_log_line(row), flush=True)   # one line in the terminal for each new post
            else:
                rows = like_post(self.server.db_path, data.get("post_id"), data.get("name"))
                self.send_json(201, like_counts_to_json(rows))
        except RuleBroken as problem:
            self.send_json(400, {"error": str(problem)})

    def do_PUT(self):
        if urlparse(self.path).path != "/posts":
            self.send_json(404, {"error": "You can only edit a post at /posts"})
            return
        data = self.read_json()
        if data is None:
            return
        try:
            row = edit_post(self.server.db_path, data.get("post_id"), data.get("name"),
                            data.get("text"))
        except RuleBroken as problem:
            self.send_json(400, {"error": str(problem)})
            return
        self.send_json(200, post_to_json(row))

    def do_DELETE(self):
        path = urlparse(self.path).path
        if path not in ("/posts", "/likes"):
            self.send_json(404, {"error": "You can only delete a post at /posts, or a like at /likes"})
            return
        data = self.read_json()
        if data is None:
            return
        try:
            if path == "/posts":
                row = delete_post(self.server.db_path, data.get("post_id"), data.get("name"))
                self.send_json(200, post_to_json(row))
            else:
                rows = unlike_post(self.server.db_path, data.get("post_id"), data.get("name"))
                self.send_json(200, like_counts_to_json(rows))
        except RuleBroken as problem:
            self.send_json(400, {"error": str(problem)})

    def read_json(self):
        """Return the request's JSON object, or send a 400 and return None."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length))
        except ValueError:
            self.send_json(400, {"error": "The request must be JSON."})
            return None
        if not isinstance(data, dict):
            self.send_json(400, {"error": "The request must be a JSON object."})
            return None
        return data

    def send_json(self, status, data):
        body = json.dumps(data).encode("utf-8")
        self.send_answer(status, "application/json; charset=utf-8", body)

    def send_answer(self, status, content_type, body):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Each window asks for new posts, likes and changes every second. Printing
        # all of those questions would fill the screen, so they are not printed.
        if self.command == "GET" and self.path.startswith(("/posts", "/likes", "/changes")):
            return
        BaseHTTPRequestHandler.log_message(self, format, *args)


# ============================================================================
#  MODEL
#  The rules a post must follow, and the database that keeps the posts.
#  Three tables: users (each person once), posts (each post points at its
#  author by the author's id, and a reply also points at the post it answers;
#  a deleted post keeps its row, with its text erased, so its replies keep their place)
#  and likes (one row for each post and user who liked it).
#  A new rule goes here, never in the controller or the view.
# ============================================================================

MAX_TEXT = 280
MAX_AUTHOR = 40


class RuleBroken(Exception):
    """A post broke one of the rules. The message says which rule."""


def connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row  # so a row can be read as row["author"]
    connection.execute("PRAGMA foreign_keys = ON")  # a post must point at a real user
    return connection


def create_tables(db_path):
    connection = connect(db_path)
    old = [c["name"] for c in connection.execute("PRAGMA table_info(posts)")]
    if old and "author_id" not in old:
        connection.close()
        raise SystemExit("timeline.db was made by an older version of Timeline. "
                         "Run `make reset`, then start the server again.")
    connection.execute("CREATE TABLE IF NOT EXISTS users ("
                       "id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
    # reply_to is empty (NULL) for a post, and the id of the post it answers for a reply.
    # edited_at is empty until the author edits the post.
    # deleted_at is empty until the author deletes the post.
    connection.execute("CREATE TABLE IF NOT EXISTS posts ("
                       "id INTEGER PRIMARY KEY, "
                       "author_id INTEGER NOT NULL REFERENCES users(id), "
                       "text TEXT NOT NULL, posted_at TEXT NOT NULL, "
                       "reply_to INTEGER REFERENCES posts(id), "
                       "edited_at TEXT, deleted_at TEXT)")
    # A timeline.db from before replies, edits and deleting has no such columns.
    # Add them, empty, so the posts already saved are kept.
    if old and "reply_to" not in old:
        connection.execute("ALTER TABLE posts ADD COLUMN reply_to INTEGER REFERENCES posts(id)")
    if old and "edited_at" not in old:
        connection.execute("ALTER TABLE posts ADD COLUMN edited_at TEXT")
    if old and "deleted_at" not in old:
        connection.execute("ALTER TABLE posts ADD COLUMN deleted_at TEXT")
    # One row for each like: which post, and which user liked it.
    # The primary key is the pair, so the database keeps each pair only once:
    # the same user cannot like the same post twice.
    connection.execute("CREATE TABLE IF NOT EXISTS likes ("
                       "post_id INTEGER NOT NULL REFERENCES posts(id), "
                       "user_id INTEGER NOT NULL REFERENCES users(id), "
                       "PRIMARY KEY (post_id, user_id))")
    connection.commit()
    connection.close()


# Each post, with its author's name looked up in users. The view reads row["author"].
POSTS_WITH_AUTHORS = ("SELECT posts.id, users.name AS author, posts.text, posts.posted_at, "
                      "posts.reply_to, posts.edited_at, posts.deleted_at "
                      "FROM posts JOIN users ON users.id = posts.author_id")

# How many likes each post has, and whether one name is among them (1) or not (0).
# The count is worked out from the rows, never stored.
LIKE_COUNTS = ("SELECT likes.post_id, COUNT(*) AS likes, MAX(users.name = ?) AS you_liked "
               "FROM likes JOIN users ON users.id = likes.user_id "
               "GROUP BY likes.post_id ORDER BY likes.post_id")


def check_name(name):
    """Return the name without extra spaces, or raise RuleBroken."""
    name = name.strip() if isinstance(name, str) else ""
    if name == "":
        raise RuleBroken("The name must not be empty.")
    if len(name) > MAX_AUTHOR:
        raise RuleBroken(f"The name must be {MAX_AUTHOR} characters or fewer.")
    return name


def check_text(text):
    """Return the text without extra spaces, or raise RuleBroken."""
    text = text.strip() if isinstance(text, str) else ""
    if text == "":
        raise RuleBroken("The post must not be empty.")
    if len(text) > MAX_TEXT:
        raise RuleBroken(f"The post must be {MAX_TEXT} characters or fewer.")
    return text


def check_rules(author, text):
    """Return the author and text without extra spaces, or raise RuleBroken."""
    return check_name(author), check_text(text)


def find_post(connection, post_id, field="post_id"):
    """Return the saved post with this id, or raise RuleBroken.
    A deleted post counts as missing: it cannot be liked, edited, replied to or deleted again."""
    # JSON true and false count as whole numbers in Python, so they are refused by name.
    if not isinstance(post_id, int) or isinstance(post_id, bool):
        raise RuleBroken(f"'{field}' must be a whole number.")
    row = connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id = ?", (post_id,)).fetchone()
    if row is None:
        raise RuleBroken(f"There is no post {post_id}.")
    if row["deleted_at"] is not None:
        raise RuleBroken(f"Post {post_id} was deleted.")
    return row


def user_id_for(connection, name):
    """Return the id of the user with this name, adding the user the first time."""
    row = connection.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
    if row is not None:
        return row["id"]
    return connection.execute("INSERT INTO users (name) VALUES (?)", (name,)).lastrowid


def save_post(db_path, author, text, reply_to=None):
    """Check the rules, save the post, and return the saved row.

    reply_to is None for a new post, or the id of the post this one answers.
    """
    author, text = check_rules(author, text)
    connection = connect(db_path)
    try:
        if reply_to is not None:
            find_post(connection, reply_to, "reply_to")
        author_id = user_id_for(connection, author)
        cursor = connection.execute(
            "INSERT INTO posts (author_id, text, posted_at, reply_to) VALUES (?, ?, ?, ?)",
            (author_id, text, time.strftime("%H:%M"), reply_to))
        connection.commit()
        return find_post(connection, cursor.lastrowid)
    finally:
        connection.close()


def edit_post(db_path, post_id, name, text):
    """Check the rules, change the post's text, and return the changed row."""
    name, text = check_rules(name, text)
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author"] != name:
            raise RuleBroken("You can only edit your own post.")
        connection.execute("UPDATE posts SET text = ?, edited_at = ? WHERE id = ?",
                           (text, time.strftime("%H:%M"), post_id))
        connection.commit()
        return find_post(connection, post_id)
    finally:
        connection.close()


def delete_post(db_path, post_id, name):
    """Check the rules, erase the post's text and likes, and return the deleted row.

    The row itself stays, so that the replies to it still point at a post.
    """
    name = check_name(name)
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author"] != name:
            raise RuleBroken("You can only delete your own post.")
        connection.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
        connection.execute("UPDATE posts SET text = '', edited_at = NULL, deleted_at = ? "
                           "WHERE id = ?", (time.strftime("%H:%M"), post_id))
        connection.commit()
        return connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id = ?",
                                  (post_id,)).fetchone()
    finally:
        connection.close()


def posts_after(db_path, after):
    """Return every post with an id larger than `after`, oldest first."""
    connection = connect(db_path)
    rows = connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id > ? ORDER BY posts.id",
                              (after,)).fetchall()
    connection.close()
    return rows


def changed_posts(db_path):
    """Return every post that has been edited or deleted, oldest first."""
    connection = connect(db_path)
    rows = connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.edited_at IS NOT NULL "
                              "OR posts.deleted_at IS NOT NULL ORDER BY posts.id").fetchall()
    connection.close()
    return rows


def like_post(db_path, post_id, name):
    """Check the rules, save the like, and return every post's likes, as like_counts does."""
    name = check_name(name)
    connection = connect(db_path)
    try:
        find_post(connection, post_id)
        user_id = user_id_for(connection, name)
        try:
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)",
                               (post_id, user_id))
        except sqlite3.IntegrityError:
            # The primary key refused a second row for this post and this user.
            raise RuleBroken("You already liked this post.")
        connection.commit()
    finally:
        connection.close()
    return like_counts(db_path, name)


def unlike_post(db_path, post_id, name):
    """Check the rules, remove the like, and return every post's likes, as like_counts does."""
    name = check_name(name)
    connection = connect(db_path)
    try:
        find_post(connection, post_id)
        cursor = connection.execute(
            "DELETE FROM likes WHERE post_id = ? "
            "AND user_id = (SELECT id FROM users WHERE name = ?)", (post_id, name))
        if cursor.rowcount == 0:
            raise RuleBroken("You have not liked this post.")
        connection.commit()
    finally:
        connection.close()
    return like_counts(db_path, name)


def like_counts(db_path, name=""):
    """Return the number of likes of every post that has at least one,
    and whether `name` is one of the people who liked it."""
    name = name.strip() if isinstance(name, str) else ""
    connection = connect(db_path)
    rows = connection.execute(LIKE_COUNTS, (name,)).fetchall()
    connection.close()
    return rows


# ============================================================================
#  VIEW
#  Turns database rows into the JSON the page reads.
# ============================================================================

def post_to_json(row):
    return {"id": row["id"], "author": row["author"],
            "text": row["text"], "posted_at": row["posted_at"],
            "reply_to": row["reply_to"], "edited_at": row["edited_at"],
            "deleted_at": row["deleted_at"]}


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


# ============================================================================
#  Starting the server
# ============================================================================

def make_server(port, db_path):
    create_tables(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), TimelineHandler)
    server.db_path = db_path
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Timeline server.")
    parser.add_argument("--port", type=int, default=8009)
    port = parser.parse_args().port
    server = make_server(port, DB_PATH)
    print("Timeline is running at http://localhost:" + str(port))
    print("The posts are kept in " + DB_PATH)
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    server.server_close()
