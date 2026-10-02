"""Timeline: the MODEL. The rules, and the database that keeps everything.

The tables:
  users     each person once, with a hash of their password (never the password), and a bio
  sessions  one row for each logged-in browser, with a hash of its token
  posts     each post points at its author by id; a reply also points at the post
            it answers; a deleted post keeps its row, with its text erased;
            a repost is a row with no words that points at the post it shares
  likes     one row for each post and user who liked it
  follows   one row for each person and someone they follow
  uploads   each uploaded picture; the file itself is in the uploads folder
  post_tags each #tag in each post, so that tags can be found fast
  bookmarks each person's saved posts; only they can see them
  notifications  what happened to each person; only they can see theirs
  messages  private messages between two people; only those two can read them

Only this file reads or writes the database. The controller (server.py) asks it
to do things; a rule that is broken comes back as RuleBroken, with a message
that says which rule.
"""

import hashlib
import hmac
import os
import re
import secrets
import sqlite3
import time

# The database file, next to this file. The server creates it when it starts.
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "timeline.db")


MAX_TEXT = 280
MAX_NAME = 40
MIN_PASSWORD = 8
MAX_PASSWORD = 200
MAX_BIO = 160
MAX_UPLOAD = 2 * 1024 * 1024   # 2 MB for one picture
MAX_QUERY = 100
MAX_MESSAGE = 1000

# A #tag or an @name: letters (of any language), numbers and _. \w means exactly that.
# (?<!\w): only when no letter comes right before, so "a@b.c" has no @name in it.
TAG = re.compile(r"(?<!\w)#(\w{1,50})")
MENTION = re.compile(r"(?<!\w)@(\w{1,40})")

# The pictures that may be uploaded, known by their first bytes, never by their name:
# a file called "photo.jpg" can be anything. SVG is not here, because it can hold code.
PICTURE_TYPES = [
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"GIF87a", "image/gif", ".gif"),
    (b"GIF89a", "image/gif", ".gif"),
]
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
    had_tags = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'post_tags'").fetchone()
    connection.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE COLLATE NOCASE,  -- 'aiko' and 'Aiko' are the same name
            password_hash TEXT NOT NULL,               -- see hash_password; never the password
            joined_at TEXT NOT NULL,
            bio TEXT NOT NULL DEFAULT '',              -- a few words about themselves
            avatar_id INTEGER REFERENCES uploads(id)); -- their picture, or empty

        -- Each uploaded picture. The file is in the uploads folder next to the database,
        -- under a random name; the name the person gave it is never used.
        CREATE TABLE IF NOT EXISTS uploads (
            id INTEGER PRIMARY KEY,
            owner_id INTEGER NOT NULL REFERENCES users(id),
            file_name TEXT NOT NULL UNIQUE,
            content_type TEXT NOT NULL,
            uploaded_at TEXT NOT NULL);

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
            deleted_at TEXT,                           -- empty until the author deletes it
            picture_id INTEGER REFERENCES uploads(id), -- a picture in the post, or empty
            repost_of INTEGER REFERENCES posts(id),    -- a repost: the post it shares; it has no words
            quote_of INTEGER REFERENCES posts(id));    -- a quote: the post it shows under its words

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
    # Columns that later versions added. An older timeline.db gets them, empty, so nothing is lost.
    add_missing_columns(connection, "users", {"bio": "TEXT NOT NULL DEFAULT ''",
                                              "avatar_id": "INTEGER REFERENCES uploads(id)"})
    add_missing_columns(connection, "posts", {"picture_id": "INTEGER REFERENCES uploads(id)",
                                              "repost_of": "INTEGER REFERENCES posts(id)",
                                              "quote_of": "INTEGER REFERENCES posts(id)"})
    # Nobody reposts the same post twice: unique, but only among reposts that are not deleted,
    # so that a repost can be undone and done again. Even code that skips the model cannot break it.
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_repost_each ON posts (author_id, repost_of) "
                       "WHERE repost_of IS NOT NULL AND deleted_at IS NULL")
    # What happened to each person: someone liked, reposted, quoted or replied to their post,
    # mentioned them, or followed them. post_id is the post it is about (empty for a follow).
    connection.execute("CREATE TABLE IF NOT EXISTS notifications ("
                       "id INTEGER PRIMARY KEY, "
                       "user_id INTEGER NOT NULL REFERENCES users(id), "      # who it is for
                       "actor_id INTEGER NOT NULL REFERENCES users(id), "     # who did it
                       "kind TEXT NOT NULL CHECK (kind IN "
                       "('like', 'repost', 'quote', 'reply', 'mention', 'follow')), "
                       "post_id INTEGER REFERENCES posts(id), "
                       "created_at TEXT NOT NULL, read_at TEXT)")
    # The same thing is told only once, even if it is done, undone and done again.
    connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS one_notification_each ON notifications "
                       "(user_id, actor_id, kind, IFNULL(post_id, 0))")
    # Private messages between two people. Only those two can read them.
    connection.execute("CREATE TABLE IF NOT EXISTS messages ("
                       "id INTEGER PRIMARY KEY, "
                       "sender_id INTEGER NOT NULL REFERENCES users(id), "
                       "receiver_id INTEGER NOT NULL REFERENCES users(id), "
                       "text TEXT NOT NULL, sent_at TEXT NOT NULL, read_at TEXT, "
                       "CHECK (sender_id != receiver_id))")
    # Each person's saved posts. Only they can see them.
    connection.execute("CREATE TABLE IF NOT EXISTS bookmarks ("
                       "user_id INTEGER NOT NULL REFERENCES users(id), "
                       "post_id INTEGER NOT NULL REFERENCES posts(id), saved_at TEXT NOT NULL, "
                       "PRIMARY KEY (user_id, post_id))")
    # Each #tag in each post, in small letters, so that a tag can be found fast.
    connection.execute("CREATE TABLE IF NOT EXISTS post_tags ("
                       "post_id INTEGER NOT NULL REFERENCES posts(id), tag TEXT NOT NULL, "
                       "PRIMARY KEY (post_id, tag))")
    if not had_tags:
        # Posts written before tags were kept: find their tags now.
        for post in connection.execute("SELECT id, text FROM posts WHERE deleted_at IS NULL").fetchall():
            save_tags(connection, post["id"], post["text"])
    connection.commit()
    connection.close()


def add_missing_columns(connection, table, columns):
    """Add each column (name: SQL type) that the table does not have yet."""
    existing = {column["name"] for column in connection.execute(f"PRAGMA table_info({table})")}
    for name, definition in columns.items():
        if name not in existing:
            connection.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


# Each post, with its author's name looked up in users. The view reads row["author"].
POSTS_WITH_AUTHORS = ("SELECT posts.id, posts.author_id, users.name AS author, posts.text, "
                      "posts.posted_at, posts.reply_to, posts.edited_at, posts.deleted_at, "
                      "posts.picture_id, pictures.file_name AS picture_file, "
                      "posts.repost_of, posts.quote_of "
                      "FROM posts JOIN users ON users.id = posts.author_id "
                      "LEFT JOIN uploads AS pictures ON pictures.id = posts.picture_id")

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
    # So that @name always works. \w is any letter (in any language), number or _.
    if not re.fullmatch(r"\w+", name):
        raise RuleBroken("A name may only have letters, numbers and _, with no spaces.")
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
    """Return the logged-in user (id, name and bio) for this token, or None."""
    if not isinstance(token, str) or token == "":
        return None
    connection = connect(db_path)
    row = connection.execute(
        "SELECT users.id, users.name, users.bio, avatars.file_name AS avatar_file "
        "FROM sessions JOIN users ON users.id = sessions.user_id "
        "LEFT JOIN uploads AS avatars ON avatars.id = users.avatar_id "
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
    """Return a person's name, bio, when they joined, how many posts they have (not deleted
    ones), how many followers and followed people they have, and whether the viewer follows them."""
    connection = connect(db_path)
    try:
        user = find_user(connection, name)
        return connection.execute(
            "SELECT name, bio, joined_at, "
            "(SELECT file_name FROM uploads WHERE id = users.avatar_id) AS avatar_file, "
            "(SELECT COUNT(*) FROM posts WHERE author_id = users.id AND deleted_at IS NULL "
            "AND repost_of IS NULL) AS posts, "
            "(SELECT COUNT(*) FROM follows WHERE followed_id = users.id) AS followers, "
            "(SELECT COUNT(*) FROM follows WHERE follower_id = users.id) AS following, "
            "EXISTS (SELECT 1 FROM follows WHERE follower_id = ? AND followed_id = users.id) "
            "AS you_follow "
            "FROM users WHERE id = ?", (viewer_id, user["id"])).fetchone()
    finally:
        connection.close()


def check_bio(bio):
    """Return the bio without extra spaces, or raise RuleBroken. An empty bio is allowed."""
    if bio is None:
        return ""
    if not isinstance(bio, str):
        raise RuleBroken("The bio must be text.")
    bio = bio.strip()
    if len(bio) > MAX_BIO:
        raise RuleBroken(f"The bio must be {MAX_BIO} characters or fewer.")
    return bio


def edit_profile(db_path, user_id, bio):
    """Check the rules, and change this user's bio."""
    bio = check_bio(bio)
    connection = connect(db_path)
    connection.execute("UPDATE users SET bio = ? WHERE id = ?", (bio, user_id))
    connection.commit()
    connection.close()


def set_avatar(db_path, user_id, upload_id):
    """Make an unused upload of this user's their picture, or remove their picture (None).
    The old picture, if any, is deleted."""
    connection = connect(db_path)
    try:
        if upload_id is not None:
            find_unused_upload(connection, upload_id, user_id)
        old = connection.execute("SELECT avatar_id FROM users WHERE id = ?", (user_id,)).fetchone()
        connection.execute("UPDATE users SET avatar_id = ? WHERE id = ?", (upload_id, user_id))
        if old["avatar_id"] is not None:
            remove_upload(connection, db_path, old["avatar_id"])
        connection.commit()
    finally:
        connection.close()


def people(db_path):
    """Return everyone's name and picture, A to Z, so that the page can draw their avatars."""
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT users.name, avatars.file_name AS avatar_file FROM users "
        "LEFT JOIN uploads AS avatars ON avatars.id = users.avatar_id "
        "ORDER BY users.name COLLATE NOCASE").fetchall()
    connection.close()
    return rows


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
        notify(connection, person["id"], user_id, "follow")
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
        unnotify(connection, person["id"], user_id, "follow")
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


# ---- Pictures ----

def uploads_dir(db_path):
    """The folder for uploaded pictures: next to the database, so a test's pictures stay with
    the test's database."""
    return os.path.join(os.path.dirname(os.path.abspath(db_path)), "uploads")


def picture_type(data):
    """Return (content type, file ending) for a picture we accept, or None."""
    for start, content_type, ending in PICTURE_TYPES:
        if data.startswith(start):
            return content_type, ending
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def save_upload(db_path, user_id, data):
    """Check the rules, keep the picture under a new random name, and return its row."""
    if not isinstance(data, bytes) or len(data) == 0:
        raise RuleBroken("The picture is empty.")
    if len(data) > MAX_UPLOAD:
        raise RuleBroken(f"A picture must be {MAX_UPLOAD // (1024 * 1024)} MB or smaller.")
    kind = picture_type(data)
    if kind is None:
        raise RuleBroken("Only JPEG, PNG, GIF and WebP pictures are allowed.")
    content_type, ending = kind
    file_name = secrets.token_urlsafe(18) + ending
    folder = uploads_dir(db_path)
    os.makedirs(folder, exist_ok=True)
    with open(os.path.join(folder, file_name), "wb") as file:
        file.write(data)
    connection = connect(db_path)
    try:
        cursor = connection.execute(
            "INSERT INTO uploads (owner_id, file_name, content_type, uploaded_at) VALUES (?, ?, ?, ?)",
            (user_id, file_name, content_type, now()))
        connection.commit()
        return connection.execute("SELECT * FROM uploads WHERE id = ?", (cursor.lastrowid,)).fetchone()
    finally:
        connection.close()


def find_unused_upload(connection, upload_id, user_id):
    """Return the upload, or raise RuleBroken: it must exist, be this user's, and not be used yet
    (in a post, or as anyone's picture)."""
    if not isinstance(upload_id, int) or isinstance(upload_id, bool):
        raise RuleBroken("'picture_id' must be a whole number.")
    upload = connection.execute("SELECT * FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    if upload is None:
        raise NotFound(f"There is no picture {upload_id}.")
    if upload["owner_id"] != user_id:
        raise RuleBroken("You can only use your own pictures.")
    used = connection.execute(
        "SELECT EXISTS (SELECT 1 FROM posts WHERE picture_id = ?) "
        "OR EXISTS (SELECT 1 FROM users WHERE avatar_id = ?)", (upload_id, upload_id)).fetchone()[0]
    if used:
        raise RuleBroken("That picture is already used.")
    return upload


def remove_upload(connection, db_path, upload_id):
    """Delete an upload's row and its file. The caller has made sure nothing points at it."""
    upload = connection.execute("SELECT file_name FROM uploads WHERE id = ?", (upload_id,)).fetchone()
    connection.execute("DELETE FROM uploads WHERE id = ?", (upload_id,))
    try:
        os.remove(os.path.join(uploads_dir(db_path), upload["file_name"]))
    except OSError:
        pass   # already gone


def upload_file(db_path, file_name):
    """Return (the file's full path, its content type) for a saved picture, or raise NotFound.
    Only names that are in the uploads table are ever opened."""
    connection = connect(db_path)
    upload = connection.execute("SELECT file_name, content_type FROM uploads WHERE file_name = ?",
                                (file_name,)).fetchone()
    connection.close()
    if upload is None:
        raise NotFound("There is no such picture.")
    return os.path.join(uploads_dir(db_path), upload["file_name"]), upload["content_type"]


# ---- Posts ----

def check_text(text, has_picture=False):
    """Return the text without extra spaces, or raise RuleBroken.
    A post with a picture may have no text."""
    text = text.strip() if isinstance(text, str) else ""
    if text == "" and not has_picture:
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


def find_original(connection, post_id, field="post_id"):
    """Like find_post, but a repost leads to the post it shares: liking, answering, quoting or
    reposting a repost acts on the original post."""
    row = find_post(connection, post_id, field)
    if row["repost_of"] is not None:
        row = find_post(connection, row["repost_of"], field)
    return row


def save_post(db_path, user_id, text, reply_to=None, posted_at=None, picture_id=None, quote_of=None):
    """Check the rules, save the post, and return the saved row.

    reply_to is None for a new post, or the id of the post this one answers.
    posted_at is None for now; seed.py gives an earlier time for its made-up posts.
    picture_id is None, or an upload of this user's that is not used yet.
    quote_of is None, or the id of the post this one quotes.
    """
    text = check_text(text, has_picture=picture_id is not None)
    if reply_to is not None and quote_of is not None:
        raise RuleBroken("A post can answer a post or quote one, not both.")
    connection = connect(db_path)
    try:
        answered = quoted = None
        if reply_to is not None:
            answered = find_original(connection, reply_to, "reply_to")
            reply_to = answered["id"]
        if quote_of is not None:
            quoted = find_original(connection, quote_of, "quote_of")
            quote_of = quoted["id"]
        if picture_id is not None:
            find_unused_upload(connection, picture_id, user_id)
        cursor = connection.execute(
            "INSERT INTO posts (author_id, text, posted_at, reply_to, picture_id, quote_of) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, text, posted_at or now(), reply_to, picture_id, quote_of))
        new_id = cursor.lastrowid
        save_tags(connection, new_id, text)
        if answered:
            notify(connection, answered["author_id"], user_id, "reply", new_id)
        if quoted:
            notify(connection, quoted["author_id"], user_id, "quote", new_id)
        notify_mentions(connection, user_id, new_id, text)
        connection.commit()
        return find_post(connection, new_id)
    finally:
        connection.close()


def add_picture(db_path, user_id, post_id, picture_id):
    """Check the rules, and add a picture to a post that has none. seed.py uses this to give its
    made-up posts pictures; on the page, a picture is added when the post is written."""
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author_id"] != user_id:
            raise RuleBroken("You can only add a picture to your own post.")
        if post["repost_of"] is not None:
            raise RuleBroken("A repost cannot have a picture.")
        if post["picture_id"] is not None:
            raise RuleBroken("This post already has a picture.")
        find_unused_upload(connection, picture_id, user_id)
        connection.execute("UPDATE posts SET picture_id = ? WHERE id = ?", (picture_id, post_id))
        connection.commit()
        return find_post(connection, post_id)
    finally:
        connection.close()


def edit_post(db_path, user_id, post_id, text):
    """Check the rules, change the post's text, and return the changed row."""
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author_id"] != user_id:
            raise RuleBroken("You can only edit your own post.")
        if post["repost_of"] is not None:
            raise RuleBroken("A repost has no words to edit.")
        text = check_text(text, has_picture=post["picture_id"] is not None)
        connection.execute("UPDATE posts SET text = ?, edited_at = ? WHERE id = ?",
                           (text, now(), post_id))
        save_tags(connection, post_id, text)
        notify_mentions(connection, user_id, post_id, text)   # only new @names hear of it
        connection.commit()
        return find_post(connection, post_id)
    finally:
        connection.close()


def delete_post(db_path, user_id, post_id):
    """Check the rules, erase the post's text, picture and likes, and return the deleted row.

    The row itself stays, so that the replies to it still point at a post.
    """
    connection = connect(db_path)
    try:
        post = find_post(connection, post_id)
        if post["author_id"] != user_id:
            raise RuleBroken("You can only delete your own post.")
        connection.execute("DELETE FROM likes WHERE post_id = ?", (post_id,))
        connection.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
        connection.execute("DELETE FROM bookmarks WHERE post_id = ?", (post_id,))
        connection.execute("DELETE FROM notifications WHERE post_id = ?", (post_id,))
        connection.execute("UPDATE posts SET text = '', edited_at = NULL, deleted_at = ?, "
                           "picture_id = NULL WHERE id = ?", (now(), post_id))
        if post["picture_id"] is not None:
            remove_upload(connection, db_path, post["picture_id"])
        connection.commit()
        return connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id = ?",
                                  (post_id,)).fetchone()
    finally:
        connection.close()


def tags_in(text):
    """The #tags in a text, in small letters, each once: "#Kyoto trip #kyoto" → ["kyoto"]."""
    return sorted({tag.lower() for tag in TAG.findall(text)})


def mentions_in(text):
    """The @names in a text, each once, as written."""
    seen = {}
    for name in MENTION.findall(text):
        seen.setdefault(name.lower(), name)
    return list(seen.values())


def save_tags(connection, post_id, text):
    """Keep a post's #tags in post_tags, in place of the ones it had before."""
    connection.execute("DELETE FROM post_tags WHERE post_id = ?", (post_id,))
    connection.executemany("INSERT INTO post_tags (post_id, tag) VALUES (?, ?)",
                           [(post_id, tag) for tag in tags_in(text)])


def search(db_path, query):
    """Find posts and people. "#kyoto" finds posts with that tag; anything else finds posts with
    those words, and people whose name or bio has them. Returns (post ids, people), newest first."""
    query = query.strip() if isinstance(query, str) else ""
    if query == "":
        raise RuleBroken("Type something to search for.")
    if len(query) > MAX_QUERY:
        raise RuleBroken(f"A search must be {MAX_QUERY} characters or fewer.")
    connection = connect(db_path)
    try:
        if query.startswith("#"):
            posts = connection.execute(
                "SELECT posts.id FROM post_tags JOIN posts ON posts.id = post_tags.post_id "
                "WHERE post_tags.tag = ? AND posts.deleted_at IS NULL ORDER BY posts.id DESC LIMIT 100",
                (query[1:].lower(),)).fetchall()
            return [row["id"] for row in posts], []
        # In LIKE, % and _ mean "anything"; a \ in front makes them ordinary letters again.
        pattern = "%" + query.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        posts = connection.execute(
            "SELECT id FROM posts WHERE text LIKE ? ESCAPE '\\' AND deleted_at IS NULL "
            "AND repost_of IS NULL ORDER BY id DESC LIMIT 100", (pattern,)).fetchall()
        found = connection.execute(
            "SELECT users.name, users.bio, avatars.file_name AS avatar_file FROM users "
            "LEFT JOIN uploads AS avatars ON avatars.id = users.avatar_id "
            "WHERE users.name LIKE ? ESCAPE '\\' OR users.bio LIKE ? ESCAPE '\\' "
            "ORDER BY users.name COLLATE NOCASE LIMIT 20", (pattern, pattern)).fetchall()
        return [row["id"] for row in posts], found
    finally:
        connection.close()


def repost(db_path, user_id, post_id, posted_at=None):
    """Check the rules, share the post with your followers, and return the new repost's row."""
    connection = connect(db_path)
    try:
        original = find_original(connection, post_id)
        try:
            cursor = connection.execute(
                "INSERT INTO posts (author_id, text, posted_at, repost_of) VALUES (?, '', ?, ?)",
                (user_id, posted_at or now(), original["id"]))
        except sqlite3.IntegrityError:
            # The index one_repost_each refused a second live repost of this post by this user.
            raise RuleBroken("You already reposted this post.")
        notify(connection, original["author_id"], user_id, "repost", original["id"])
        connection.commit()
        return find_post(connection, cursor.lastrowid)
    finally:
        connection.close()


def undo_repost(db_path, user_id, post_id):
    """Check the rules, take back your repost of this post, and return the repost's row (deleted)."""
    connection = connect(db_path)
    try:
        original = find_original(connection, post_id)
        mine = connection.execute(
            "SELECT id FROM posts WHERE author_id = ? AND repost_of = ? AND deleted_at IS NULL",
            (user_id, original["id"])).fetchone()
        if mine is None:
            raise RuleBroken("You have not reposted this post.")
        connection.execute("UPDATE posts SET deleted_at = ? WHERE id = ?", (now(), mine["id"]))
        unnotify(connection, original["author_id"], user_id, "repost", original["id"])
        connection.commit()
        return connection.execute(POSTS_WITH_AUTHORS + " WHERE posts.id = ?", (mine["id"],)).fetchone()
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


# ---- The sidebar: what is trending, and who to follow ----

def trends(db_path, days=7, limit=5):
    """The #tags used in the most posts in the last few days, with how many posts."""
    since = time.strftime("%Y-%m-%d %H:%M", time.localtime(time.time() - days * 24 * 60 * 60))
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT post_tags.tag, COUNT(*) AS posts FROM post_tags JOIN posts ON posts.id = post_tags.post_id "
        "WHERE posts.deleted_at IS NULL AND posts.posted_at >= ? "
        "GROUP BY post_tags.tag ORDER BY posts DESC, post_tags.tag LIMIT ?", (since, limit)).fetchall()
    connection.close()
    return rows


def suggestions(db_path, viewer_id=None, limit=3):
    """People to follow: the ones with the most followers, leaving out the viewer and
    everyone the viewer already follows."""
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT users.name, users.bio, avatars.file_name AS avatar_file, "
        "(SELECT COUNT(*) FROM follows WHERE followed_id = users.id) AS followers FROM users "
        "LEFT JOIN uploads AS avatars ON avatars.id = users.avatar_id "
        "WHERE users.id IS NOT ? AND users.id NOT IN "
        "(SELECT followed_id FROM follows WHERE follower_id IS ?) "
        "ORDER BY followers DESC, users.name COLLATE NOCASE LIMIT ?",
        (viewer_id, viewer_id, limit)).fetchall()
    connection.close()
    return rows


# ---- Notifications ----

def notify(connection, user_id, actor_id, kind, post_id=None):
    """Tell user_id that actor_id did something. Nobody is told about their own actions,
    and the same thing is told only once."""
    if user_id == actor_id:
        return
    connection.execute("INSERT OR IGNORE INTO notifications (user_id, actor_id, kind, post_id, created_at) "
                       "VALUES (?, ?, ?, ?, ?)", (user_id, actor_id, kind, post_id, now()))


def unnotify(connection, user_id, actor_id, kind, post_id=None):
    """Take a notification back, when its action is undone (an unlike, an unfollow)."""
    connection.execute("DELETE FROM notifications WHERE user_id = ? AND actor_id = ? AND kind = ? "
                       "AND IFNULL(post_id, 0) = IFNULL(?, 0)", (user_id, actor_id, kind, post_id))


def notify_mentions(connection, author_id, post_id, text):
    """Tell each person named with @ in the text. A name nobody has is skipped."""
    for name in mentions_in(text):
        person = connection.execute("SELECT id FROM users WHERE name = ?", (name,)).fetchone()
        if person is not None:
            notify(connection, person["id"], author_id, "mention", post_id)


def notifications_of(db_path, user_id):
    """This user's notifications, newest first, with who did it. Only ever this user's own."""
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT notifications.id, notifications.kind, users.name AS actor, notifications.post_id, "
        "notifications.created_at, notifications.read_at FROM notifications "
        "JOIN users ON users.id = notifications.actor_id WHERE notifications.user_id = ? "
        "ORDER BY notifications.created_at DESC, notifications.id DESC LIMIT 100", (user_id,)).fetchall()
    connection.close()
    return rows


def unread_notifications(db_path, user_id):
    connection = connect(db_path)
    count = connection.execute("SELECT COUNT(*) FROM notifications WHERE user_id = ? AND read_at IS NULL",
                               (user_id,)).fetchone()[0]
    connection.close()
    return count


def read_notifications(db_path, user_id, before=None):
    """Mark all of this user's notifications as read
    (only those made up to `before`, when it is given; seed.py uses that)."""
    connection = connect(db_path)
    connection.execute("UPDATE notifications SET read_at = ? WHERE user_id = ? AND read_at IS NULL "
                       "AND (? IS NULL OR created_at <= ?)", (now(), user_id, before, before))
    connection.commit()
    connection.close()


# ---- Direct messages: every query is about one person's own conversations ----

def check_message(text):
    """Return the message without extra spaces, or raise RuleBroken."""
    text = text.strip() if isinstance(text, str) else ""
    if text == "":
        raise RuleBroken("The message must not be empty.")
    if len(text) > MAX_MESSAGE:
        raise RuleBroken(f"A message must be {MAX_MESSAGE} characters or fewer.")
    return text


def send_message(db_path, sender_id, to_name, text, sent_at=None):
    """Check the rules, save the message, and return it."""
    text = check_message(text)
    connection = connect(db_path)
    try:
        person = find_user(connection, to_name)
        if person["id"] == sender_id:
            raise RuleBroken("You cannot send a message to yourself.")
        cursor = connection.execute(
            "INSERT INTO messages (sender_id, receiver_id, text, sent_at) VALUES (?, ?, ?, ?)",
            (sender_id, person["id"], text, sent_at or now()))
        connection.commit()
        return connection.execute("SELECT *, 1 AS from_me FROM messages WHERE id = ?",
                                  (cursor.lastrowid,)).fetchone()
    finally:
        connection.close()


def conversations(db_path, user_id):
    """Everyone this user has messages with: the newest message of each conversation, and how
    many from them are unread. The conversation with the newest message comes first."""
    connection = connect(db_path)
    rows = connection.execute(
        "SELECT other.name, avatars.file_name AS avatar_file, last.text, last.sent_at, "
        "last.sender_id = ? AS from_me, "
        "(SELECT COUNT(*) FROM messages WHERE sender_id = other.id AND receiver_id = ? "
        "AND read_at IS NULL) AS unread "
        "FROM (SELECT CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END AS other_id, "
        "MAX(id) AS last_id FROM messages WHERE sender_id = ? OR receiver_id = ? GROUP BY other_id) AS pairs "
        "JOIN users AS other ON other.id = pairs.other_id "
        "JOIN messages AS last ON last.id = pairs.last_id "
        "LEFT JOIN uploads AS avatars ON avatars.id = other.avatar_id "
        "ORDER BY last.id DESC", (user_id, user_id, user_id, user_id, user_id)).fetchall()
    connection.close()
    return rows


def conversation(db_path, user_id, with_name):
    """The messages between this user and one other person, oldest first (the last 500)."""
    connection = connect(db_path)
    try:
        person = find_user(connection, with_name)
        rows = connection.execute(
            "SELECT * FROM (SELECT *, sender_id = ? AS from_me FROM messages "
            "WHERE (sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?) "
            "ORDER BY id DESC LIMIT 500) ORDER BY id",
            (user_id, user_id, person["id"], person["id"], user_id)).fetchall()
        return person, rows
    finally:
        connection.close()


def read_conversation(db_path, user_id, with_name, before=None):
    """Mark the messages this user got from the other person as read
    (only those sent up to `before`, when it is given; seed.py uses that)."""
    connection = connect(db_path)
    try:
        person = find_user(connection, with_name)
        connection.execute("UPDATE messages SET read_at = ? WHERE sender_id = ? AND receiver_id = ? "
                           "AND read_at IS NULL AND (? IS NULL OR sent_at <= ?)",
                           (now(), person["id"], user_id, before, before))
        connection.commit()
    finally:
        connection.close()


def unread_messages(db_path, user_id):
    connection = connect(db_path)
    count = connection.execute("SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND read_at IS NULL",
                               (user_id,)).fetchone()[0]
    connection.close()
    return count


# ---- Bookmarks ----

def bookmark(db_path, user_id, post_id):
    """Check the rules, save the post in this user's bookmarks, and return them all."""
    connection = connect(db_path)
    try:
        post_id = find_original(connection, post_id)["id"]
        try:
            connection.execute("INSERT INTO bookmarks (user_id, post_id, saved_at) VALUES (?, ?, ?)",
                               (user_id, post_id, now()))
        except sqlite3.IntegrityError:
            raise RuleBroken("You already saved this post.")
        connection.commit()
    finally:
        connection.close()
    return bookmarks_of(db_path, user_id)


def remove_bookmark(db_path, user_id, post_id):
    """Check the rules, take the post out of this user's bookmarks, and return the rest."""
    connection = connect(db_path)
    try:
        post_id = find_original(connection, post_id)["id"]
        cursor = connection.execute("DELETE FROM bookmarks WHERE user_id = ? AND post_id = ?",
                                    (user_id, post_id))
        if cursor.rowcount == 0:
            raise RuleBroken("You have not saved this post.")
        connection.commit()
    finally:
        connection.close()
    return bookmarks_of(db_path, user_id)


def bookmarks_of(db_path, user_id):
    """The ids of the posts this user saved, the latest saved first. Only ever this user's."""
    connection = connect(db_path)
    rows = connection.execute("SELECT post_id FROM bookmarks WHERE user_id = ? "
                              "ORDER BY saved_at DESC, rowid DESC", (user_id,)).fetchall()
    connection.close()
    return [row["post_id"] for row in rows]


# ---- Likes ----

def like_post(db_path, user_id, post_id):
    """Check the rules, save the like, and return every post's likes, as like_counts does."""
    connection = connect(db_path)
    try:
        post = find_original(connection, post_id)
        post_id = post["id"]
        try:
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (?, ?)",
                               (post_id, user_id))
        except sqlite3.IntegrityError:
            # The primary key refused a second row for this post and this user.
            raise RuleBroken("You already liked this post.")
        notify(connection, post["author_id"], user_id, "like", post_id)
        connection.commit()
    finally:
        connection.close()
    return like_counts(db_path, user_id)


def unlike_post(db_path, user_id, post_id):
    """Check the rules, remove the like, and return every post's likes, as like_counts does."""
    connection = connect(db_path)
    try:
        post = find_original(connection, post_id)
        post_id = post["id"]
        cursor = connection.execute("DELETE FROM likes WHERE post_id = ? AND user_id = ?",
                                    (post_id, user_id))
        if cursor.rowcount == 0:
            raise RuleBroken("You have not liked this post.")
        unnotify(connection, post["author_id"], user_id, "like", post_id)
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
