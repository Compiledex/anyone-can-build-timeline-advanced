"""Timeline: the backend. Start it with `python3 server.py`, then open http://localhost:8010

This file has three parts:
  CONTROLLER  reads each request and decides what to do
  MODEL       the rules, and the database (tables: users, sessions, posts, likes, follows)
  VIEW        turns database rows into the JSON answer
It uses only the Python standard library, so there is nothing to install.
"""

import argparse
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import threading
import time
from http.cookies import CookieError, SimpleCookie
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

# The name of the cookie that holds a logged-in browser's session token.
SESSION_COOKIE = "session"


# ============================================================================
#  CONTROLLER
#  Reads the request. Picks what to do. Asks the model. Sends the answer.
#  Each request is handled by the method named after it: POST /likes is
#  handled by post_likes. The list of them is ROUTES, at the end of this part.
# ============================================================================

class TimelineHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.route("GET")

    def do_POST(self):
        self.route("POST")

    def do_PUT(self):
        self.route("PUT")

    def do_DELETE(self):
        self.route("DELETE")

    def route(self, method):
        """Find the method for this request and run it. A broken rule becomes an error answer."""
        url = urlparse(self.path)
        if method == "GET" and url.path in PAGE_FILES:
            self.send_page(url.path)
            return
        action = ROUTES.get((method, url.path))
        if action is None:
            self.send_json(404, {"error": "There is nothing at " + method + " " + url.path})
            return
        try:
            action(self, parse_qs(url.query))
        except NotLoggedIn as problem:
            self.send_json(401, {"error": str(problem)})
        except NotFound as problem:
            self.send_json(404, {"error": str(problem)})
        except RuleBroken as problem:
            self.send_json(400, {"error": str(problem)})
        else:
            if method != "GET":
                self.server.bell.ring()   # something was saved: tell every open window

    # ---- Live updates ----

    def get_events(self, query):
        """Keep this request open, and send a short message each time the bell rings.

        This is Server-Sent Events: the page's EventSource reads the messages. "retry" asks
        the browser to connect again one second after the connection drops, and the first
        message, "hello", makes the page catch up on anything it missed while it was away.
        """
        bell = self.server.bell
        heard = bell.rings
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        try:
            self.wfile.write(b"retry: 1000\ndata: hello\n\n")
            while True:
                rings = bell.wait(heard, timeout=15)
                if rings == heard:
                    # Nothing new for 15 seconds. A line starting with ":" is a comment that the
                    # page ignores; it only keeps the connection from being closed as idle.
                    self.wfile.write(b": still here\n\n")
                else:
                    heard = rings
                    self.wfile.write(b"data: changed\n\n")
        except (BrokenPipeError, ConnectionResetError):
            pass   # the window was closed, or went to another page

    # ---- Accounts ----

    def post_signup(self, query):
        data = self.read_json()
        token = sign_up(self.db, data.get("name"), data.get("password"))
        self.send_me(201, current_user(self.db, token), cookie=token)

    def post_login(self, query):
        data = self.read_json()
        token = log_in(self.db, data.get("name"), data.get("password"))
        self.send_me(200, current_user(self.db, token), cookie=token)

    def post_logout(self, query):
        log_out(self.db, self.session_token())
        self.send_me(200, None, cookie="")

    def get_me(self, query):
        self.send_me(200, current_user(self.db, self.session_token()))

    # ---- People ----

    def get_users(self, query):
        name = query.get("name", [""])[0]
        viewer = current_user(self.db, self.session_token())
        self.send_json(200, profile_to_json(profile(self.db, name, viewer["id"] if viewer else None)))

    def post_follows(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        follow(self.db, user["id"], data.get("name"))
        self.send_me(201, user)

    def delete_follows(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        unfollow(self.db, user["id"], data.get("name"))
        self.send_me(200, user)

    # ---- Posts ----

    def get_posts(self, query):
        try:
            after = int(query.get("after", ["0"])[0])
        except ValueError:
            raise RuleBroken("'after' must be a whole number.")
        self.send_json(200, posts_to_json(posts_after(self.db, after)))

    def post_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = save_post(self.db, user["id"], data.get("text"), data.get("reply_to"))
        self.send_json(201, post_to_json(row))
        print(post_to_log_line(row), flush=True)   # one line in the terminal for each new post

    def put_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = edit_post(self.db, user["id"], data.get("post_id"), data.get("text"))
        self.send_json(200, post_to_json(row))

    def delete_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = delete_post(self.db, user["id"], data.get("post_id"))
        self.send_json(200, post_to_json(row))

    def get_changes(self, query):
        self.send_json(200, posts_to_json(changed_posts(self.db)))

    # ---- Likes ----

    def get_likes(self, query):
        viewer = current_user(self.db, self.session_token())
        rows = like_counts(self.db, viewer["id"] if viewer else None)
        self.send_json(200, like_counts_to_json(rows))

    def post_likes(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(201, like_counts_to_json(like_post(self.db, user["id"], data.get("post_id"))))

    def delete_likes(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(200, like_counts_to_json(unlike_post(self.db, user["id"], data.get("post_id"))))

    # ---- Reading the request ----

    @property
    def db(self):
        return self.server.db_path

    def read_json(self):
        """Return the request's JSON object, or raise RuleBroken."""
        try:
            length = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(length) or b"{}")
        except ValueError:
            raise RuleBroken("The request must be JSON.")
        if not isinstance(data, dict):
            raise RuleBroken("The request must be a JSON object.")
        return data

    def session_token(self):
        """The session token from the request's cookie, or "" if there is none."""
        try:
            cookie = SimpleCookie(self.headers.get("Cookie") or "")
        except CookieError:
            return ""
        return cookie[SESSION_COOKIE].value if SESSION_COOKIE in cookie else ""

    def logged_in_user(self):
        """The logged-in user (id and name). The model raises NotLoggedIn if there is none."""
        return user_for_token(self.db, self.session_token())

    # ---- Sending the answer ----

    def send_page(self, path):
        file_name, content_type = PAGE_FILES[path]
        try:
            with open(os.path.join(HERE, file_name), "rb") as page_file:
                self.send_answer(200, content_type, page_file.read())
        except OSError:
            self.send_json(404, {"error": "The file " + file_name + " is missing."})

    def send_me(self, status, user, cookie=None):
        """Send who is logged in (or nobody), and the names they follow."""
        following = followed_by(self.db, user["id"]) if user else []
        self.send_json(status, me_to_json(user, following), cookie=cookie)

    def send_json(self, status, data, cookie=None):
        """Send data as JSON. With a cookie, also set the session cookie: a token logs the
        browser in, and "" logs it out."""
        headers = []
        if cookie is not None:
            # HttpOnly: the page's JavaScript cannot read it. SameSite=Strict: the browser sends it
            # only to this site, so another site cannot make your browser act as you.
            age = SESSION_DAYS * 24 * 60 * 60 if cookie else 0
            headers.append(("Set-Cookie", f"{SESSION_COOKIE}={cookie}; HttpOnly; SameSite=Strict; "
                                          f"Path=/; Max-Age={age}"))
        body = json.dumps(data).encode("utf-8")
        self.send_answer(status, "application/json; charset=utf-8", body, headers)

    def send_answer(self, status, content_type, body, headers=()):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Each window asks for new posts, likes and changes after every change anyone makes.
        # Printing all of those questions would fill the screen, so they are not printed.
        if self.command == "GET" and self.path.startswith(("/posts", "/likes", "/changes", "/me",
                                                           "/users", "/events")):
            return
        BaseHTTPRequestHandler.log_message(self, format, *args)


ROUTES = {
    ("GET", "/events"): TimelineHandler.get_events,
    ("POST", "/signup"): TimelineHandler.post_signup,
    ("POST", "/login"): TimelineHandler.post_login,
    ("POST", "/logout"): TimelineHandler.post_logout,
    ("GET", "/me"): TimelineHandler.get_me,
    ("GET", "/users"): TimelineHandler.get_users,
    ("POST", "/follows"): TimelineHandler.post_follows,
    ("DELETE", "/follows"): TimelineHandler.delete_follows,
    ("GET", "/posts"): TimelineHandler.get_posts,
    ("POST", "/posts"): TimelineHandler.post_posts,
    ("PUT", "/posts"): TimelineHandler.put_posts,
    ("DELETE", "/posts"): TimelineHandler.delete_posts,
    ("GET", "/changes"): TimelineHandler.get_changes,
    ("GET", "/likes"): TimelineHandler.get_likes,
    ("POST", "/likes"): TimelineHandler.post_likes,
    ("DELETE", "/likes"): TimelineHandler.delete_likes,
}


# ============================================================================
#  MODEL
#  The rules, and the database that keeps everything:
#    users     each person once, with a hash of their password (never the password)
#    sessions  one row for each logged-in browser, with a hash of its token
#    posts     each post points at its author by id; a reply also points at the post
#              it answers; a deleted post keeps its row, with its text erased
#    likes     one row for each post and user who liked it
#    follows   one row for each person and someone they follow
#  A new rule goes here, never in the controller or the view.
# ============================================================================

MAX_TEXT = 280
MAX_NAME = 40
MIN_PASSWORD = 8
MAX_PASSWORD = 200
# Hashing a password is slow on purpose: someone who steals the database must
# spend this much work on every single guess. The tests use fewer rounds.
PASSWORD_ROUNDS = 600_000
SESSION_DAYS = 30


class RuleBroken(Exception):
    """A request broke one of the rules. The message says which rule."""


class NotLoggedIn(RuleBroken):
    """The request needs a logged-in user, and there is none."""


class NotFound(RuleBroken):
    """The request names a post or a person that does not exist."""


def connect(db_path):
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row  # so a row can be read as row["author"]
    connection.execute("PRAGMA foreign_keys = ON")  # an id must point at a real row
    return connection


def now():
    """The time now, as 2026-10-02 15:42. Text in this form sorts in time order."""
    return time.strftime("%Y-%m-%d %H:%M")


def create_tables(db_path):
    connection = connect(db_path)
    old = [c["name"] for c in connection.execute("PRAGMA table_info(users)")]
    if old and "password_hash" not in old:
        connection.close()
        raise SystemExit("timeline.db was made by an older version of Timeline, without accounts. "
                         "Run `make reset`, then start the server again.")
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- 'aiko' and 'Aiko' are the same name
            password_hash TEXT NOT NULL,               -- see hash_password; never the password
            joined_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS sessions (
            token_hash TEXT PRIMARY KEY,               -- a hash of the token in the cookie
            user_id INTEGER NOT NULL REFERENCES users(id),
            expires_at TEXT NOT NULL);

        CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY,
            author_id INTEGER NOT NULL REFERENCES users(id),
            text TEXT NOT NULL,
            posted_at TEXT NOT NULL,
            reply_to INTEGER REFERENCES posts(id),     -- empty for a post, the answered post for a reply
            edited_at TEXT,                            -- empty until the author edits it
            deleted_at TEXT);                          -- empty until the author deletes it

        -- The primary key is the pair, so the database keeps each like only once.
        CREATE TABLE IF NOT EXISTS likes (
            post_id INTEGER NOT NULL REFERENCES posts(id),
            user_id INTEGER NOT NULL REFERENCES users(id),
            PRIMARY KEY (post_id, user_id));

        -- Who follows whom. The pair is the primary key, so you can follow someone only
        -- once, and the CHECK stops anyone from following themselves.
        CREATE TABLE IF NOT EXISTS follows (
            follower_id INTEGER NOT NULL REFERENCES users(id),
            followed_id INTEGER NOT NULL REFERENCES users(id),
            PRIMARY KEY (follower_id, followed_id),
            CHECK (follower_id != followed_id));
    """)
    connection.close()


# Each post, with its author's name looked up in users. The view reads row["author"].
POSTS_WITH_AUTHORS = ("SELECT posts.id, posts.author_id, users.name AS author, posts.text, "
                      "posts.posted_at, posts.reply_to, posts.edited_at, posts.deleted_at "
                      "FROM posts JOIN users ON users.id = posts.author_id")

# How many likes each post has, and whether one user is among them (1) or not (0 or empty).
# The count is worked out from the rows, never stored.
LIKE_COUNTS = ("SELECT post_id, COUNT(*) AS likes, MAX(user_id = ?) AS you_liked "
               "FROM likes GROUP BY post_id ORDER BY post_id")


# ---- Accounts ----

def check_name(name):
    """Return the name without extra spaces, or raise RuleBroken."""
    name = name.strip() if isinstance(name, str) else ""
    if name == "":
        raise RuleBroken("The name must not be empty.")
    if len(name) > MAX_NAME:
        raise RuleBroken(f"The name must be {MAX_NAME} characters or fewer.")
    return name


def check_password(password):
    """Return the password as it is (spaces count), or raise RuleBroken."""
    if not isinstance(password, str) or len(password) < MIN_PASSWORD:
        raise RuleBroken(f"The password must be at least {MIN_PASSWORD} characters.")
    if len(password) > MAX_PASSWORD:
        raise RuleBroken(f"The password must be {MAX_PASSWORD} characters or fewer.")
    return password


def hash_password(password):
    """Return 'pbkdf2_sha256$rounds$salt$hash'. The password cannot be read back from it.

    The salt is random for each password, so two people with the same password
    get different hashes, and a list of hashes made in advance is no help.
    """
    rounds = PASSWORD_ROUNDS
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), rounds)
    return f"pbkdf2_sha256${rounds}${salt}${digest.hex()}"


def password_matches(password, stored):
    """Hash the password the same way as the stored hash, and compare the two."""
    _, rounds, salt, digest = stored.split("$")
    attempt = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt),
                                  int(rounds))
    return hmac.compare_digest(attempt.hex(), digest)  # takes the same time, match or not


def token_hash(token):
    """The database keeps only a hash of each session token, so a copy of the
    database cannot be used to log in as anyone."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(connection, user_id):
    """Save a new session for this user, and return its token for the cookie."""
    token = secrets.token_urlsafe(32)
    expires = time.strftime("%Y-%m-%d %H:%M",
                            time.localtime(time.time() + SESSION_DAYS * 24 * 60 * 60))
    connection.execute("INSERT INTO sessions (token_hash, user_id, expires_at) VALUES (?, ?, ?)",
                       (token_hash(token), user_id, expires))
    return token


def sign_up(db_path, name, password, joined_at=None):
    """Check the rules, add the user, log them in, and return the session token.

    joined_at is None for now; seed.py gives an earlier time for its made-up people.
    """
    name = check_name(name)
    password = check_password(password)
    connection = connect(db_path)
    try:
        try:
            user_id = connection.execute(
                "INSERT INTO users (name, password_hash, joined_at) VALUES (?, ?, ?)",
                (name, hash_password(password), joined_at or now())).lastrowid
        except sqlite3.IntegrityError:
            # The UNIQUE rule on users.name refused a second user with this name.
            raise RuleBroken(f"The name {name} is taken. Pick another name, or log in.")
        token = start_session(connection, user_id)
        connection.commit()
        return token
    finally:
        connection.close()


def log_in(db_path, name, password):
    """Check the name and password, and return a new session token, or raise RuleBroken."""
    name = name.strip() if isinstance(name, str) else ""
    password = password if isinstance(password, str) else ""
    connection = connect(db_path)
    try:
        user = connection.execute("SELECT id, password_hash FROM users WHERE name = ?",
                                  (name,)).fetchone()
        # The same answer for a wrong name and a wrong password, so that
        # nobody can use this to find out which names have accounts.
        if user is None or not password_matches(password, user["password_hash"]):
            raise RuleBroken("Wrong name or password.")
        token = start_session(connection, user["id"])
        connection.commit()
        return token
    finally:
        connection.close()


def log_out(db_path, token):
    """End this session. Its token no longer logs anyone in."""
    connection = connect(db_path)
    connection.execute("DELETE FROM sessions WHERE token_hash = ?", (token_hash(token),))
    connection.commit()
    connection.close()


def current_user(db_path, token):
    """Return the logged-in user (id and name) for this token, or None."""
    if not isinstance(token, str) or token == "":
        return None
    connection = connect(db_path)
    row = connection.execute(
        "SELECT users.id, users.name FROM sessions JOIN users ON users.id = sessions.user_id "
        "WHERE sessions.token_hash = ? AND sessions.expires_at > ?",
        (token_hash(token), now())).fetchone()
    connection.close()
    return row


def user_for_token(db_path, token):
    """Like current_user, but raise NotLoggedIn instead of returning None."""
    user = current_user(db_path, token)
    if user is None:
        raise NotLoggedIn("Please log in first.")
    return user


# ---- People ----

def find_user(connection, name):
    """Return the user with this name (any capitals), or raise NotFound."""
    name = name.strip() if isinstance(name, str) else ""
    row = connection.execute("SELECT id, name, joined_at FROM users WHERE name = ?",
                             (name,)).fetchone()
    if row is None:
        raise NotFound(f"There is no one called {name or 'that'}.")
    return row


def profile(db_path, name, viewer_id=None):
    """Return a person's name, when they joined, how many posts they have (not deleted ones),
    how many followers and followed people they have, and whether the viewer follows them."""
    connection = connect(db_path)
    try:
        user = find_user(connection, name)
        return connection.execute(
            "SELECT name, joined_at, "
            "(SELECT COUNT(*) FROM posts WHERE author_id = users.id AND deleted_at IS NULL) AS posts, "
            "(SELECT COUNT(*) FROM follows WHERE followed_id = users.id) AS followers, "
            "(SELECT COUNT(*) FROM follows WHERE follower_id = users.id) AS following, "
            "EXISTS (SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = users.id) "
            "AS you_follow "
            "FROM users WHERE id = ?", (viewer_id, user["id"])).fetchone()
    finally:
        connection.close()


def follow(db_path, user_id, name):
    """Check the rules, and make this user follow the person with this name."""
    connection = connect(db_path)
    try:
        person = find_user(connection, name)
        if person["id"] == user_id:
            raise RuleBroken("You cannot follow yourself.")
        try:
            connection.execute("INSERT INTO follows (follower_id, followed_id) VALUES (?, ?)",
                               (user_id, person["id"]))
        except sqlite3.IntegrityError:
            # The primary key refused a second row for the same pair.
            raise RuleBroken(f"You already follow {person['name']}.")
        connection.commit()
    finally:
        connection.close()


def unfollow(db_path, user_id, name):
    """Check the rules, and stop this user from following the person with this name."""
    connection = connect(db_path)
    try:
        person = find_user(connection, name)
        cursor = connection.execute("DELETE FROM follows WHERE follower_id = ? AND followed_id = ?",
                                    (user_id, person["id"]))
        if cursor.rowcount == 0:
            raise RuleBroken(f"You do not follow {person['name']}.")
        connection.commit()
    finally:
        connection.close()


def followed_by(db_path, user_id):
    """Return everyone this user follows, A to Z."""
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT users.name FROM follows JOIN users ON users.id = follows.followed_id "
        "WHERE follows.follower_id = ? ORDER BY users.name COLLATE NOCASE", (user_id,)).fetchall()
    connection.close()
    return rows


# ---- Posts ----

def check_text(text):
    """Return the text without extra spaces, or raise RuleBroken."""
    text = text.strip() if isinstance(text, str) else ""
    if text == "":
        raise RuleBroken("The post must not be empty.")
    if len(text) > MAX_TEXT:
        raise RuleBroken(f"The post must be {MAX_TEXT} characters or fewer.")
    return text


def find_post(connection, post_id, field="post_id"):
    """Return the saved post with this id, or raise RuleBroken.
    A deleted post counts as missing: it cannot be liked, edited, replied to or deleted again."""
    # JSON true and false count as whole numbers in Python, so they are refused by name.
    if not isinstance(post_id, int) or isinstance(post_id, bool):
        raise RuleBroken(f"'{field}' must be a whole number.")
    row = connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id = ?", (post_id,)).fetchone()
    if row is None:
        raise NotFound(f"There is no post {post_id}.")
    if row["deleted_at"] is not None:
        raise NotFound(f"Post {post_id} was deleted.")
    return row


def save_post(db_path, user_id, text, reply_to=None, posted_at=None):
    """Check the rules, save the post, and return the saved row.

    reply_to is None for a new post, or the id of the post this one answers.
    posted_at is None for now; seed.py gives an earlier time for its made-up posts.
    """
    text = check_text(text)
    connection = connect(db_path)
    try:
        if reply_to is not None:
            find_post(connection, reply_to, "reply_to")
        cursor = connection.execute(
            "INSERT INTO posts (author_id, text, posted_at, reply_to) VALUES (?, ?, ?, ?)",
            (user_id, text, posted_at or now(), reply_to))
        connection.commit()
        return find_post(connection, cursor.lastrowid)
    finally:
        connection.close()


def edit_post(db_path, user_id, post_id, text):
    """Check the rules, change the post's text, and return the changed row."""
    text = check_text(text)
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author_id"] != user_id:
            raise RuleBroken("You can only edit your own post.")
        connection.execute("UPDATE posts SET text = ?, edited_at = ? WHERE id = ?",
                           (text, now(), post_id))
        connection.commit()
        return find_post(connection, post_id)
    finally:
        connection.close()


def delete_post(db_path, user_id, post_id):
    """Check the rules, erase the post's text and likes, and return the deleted row.

    The row itself stays, so that the replies to it still point at a post.
    """
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author_id"] != user_id:
            raise RuleBroken("You can only delete your own post.")
        connection.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
        connection.execute("UPDATE posts SET text = '', edited_at = NULL, deleted_at = ? "
                           "WHERE id = ?", (now(), post_id))
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


# ---- Likes ----

def like_post(db_path, user_id, post_id):
    """Check the rules, save the like, and return every post's likes, as like_counts does."""
    connection = connect(db_path)
    try:
        find_post(connection, post_id)
        try:
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)",
                               (post_id, user_id))
        except sqlite3.IntegrityError:
            # The primary key refused a second row for this post and this user.
            raise RuleBroken("You already liked this post.")
        connection.commit()
    finally:
        connection.close()
    return like_counts(db_path, user_id)


def unlike_post(db_path, user_id, post_id):
    """Check the rules, remove the like, and return every post's likes, as like_counts does."""
    connection = connect(db_path)
    try:
        find_post(connection, post_id)
        cursor = connection.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?",
                                    (post_id, user_id))
        if cursor.rowcount == 0:
            raise RuleBroken("You have not liked this post.")
        connection.commit()
    finally:
        connection.close()
    return like_counts(db_path, user_id)


def like_counts(db_path, viewer_id=None):
    """Return the number of likes of every post that has at least one,
    and whether the viewer (a user id, or None) is one of the people who liked it."""
    connection = connect(db_path)
    rows = connection.execute(LIKE_COUNTS, (viewer_id,)).fetchall()
    connection.close()
    return rows


# ============================================================================
#  VIEW
#  Turns database rows into the JSON the page reads.
# ============================================================================

def me_to_json(user, following=()):
    return {"name": user["name"] if user else None,
            "following": [row["name"] for row in following]}


def profile_to_json(row):
    return {"name": row["name"], "joined_at": row["joined_at"], "posts": row["posts"],
            "followers": row["followers"], "following": row["following"],
            "you_follow": row["you_follow"] == 1}


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

class Bell:
    """Rings once after every saved change. Each open /events request waits for it.

    Requests are handled at the same time, each in its own thread, so the bell uses
    a Condition: a lock that threads can also wait on until another thread wakes them.
    """

    def __init__(self):
        self.rings = 0
        self.condition = threading.Condition()

    def ring(self):
        with self.condition:
            self.rings += 1
            self.condition.notify_all()

    def wait(self, heard, timeout):
        """Wait until the bell has rung more than `heard` times, or until `timeout`
        seconds pass. Return how many times it has rung."""
        with self.condition:
            self.condition.wait_for(lambda: self.rings != heard, timeout)
            return self.rings


def make_server(port, db_path):
    create_tables(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), TimelineHandler)
    server.db_path = db_path
    server.bell = Bell()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Timeline server.")
    parser.add_argument("--port", type=int, default=8010)
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
