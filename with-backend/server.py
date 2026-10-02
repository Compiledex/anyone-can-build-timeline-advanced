"""Timeline: the backend. Start it with `python3 server.py`, then open http://localhost:8010

The backend has three parts, in three files:
  server.py   the CONTROLLER: reads each request, asks the model, sends the answer (this file)
  model.py    the MODEL: the rules, and the database
  view.py     the VIEW: turns database rows into the JSON the page reads
It uses only the Python standard library, so there is nothing to install.
"""

import argparse
import json
import os
import threading
from http.cookies import CookieError, SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import model
import view

HERE = os.path.dirname(os.path.abspath(__file__))

# The page: every file in the page/ folder, and only those, of these types.
PAGE_DIR = os.path.realpath(os.path.join(HERE, "page"))
PAGE_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
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
        action = ROUTES.get((method, url.path))
        if action is None and method == "GET" and url.path.startswith("/uploads/"):
            action = TimelineHandler.get_upload
        if action is None and method == "GET" and page_file(url.path):
            self.send_page(page_file(url.path))
            return
        if action is None:
            self.send_json(404, {"error": "There is nothing at " + method + " " + url.path})
            return
        try:
            action(self, parse_qs(url.query))
        except model.NotLoggedIn as problem:
            self.send_json(401, {"error": str(problem)})
        except model.NotFound as problem:
            self.send_json(404, {"error": str(problem)})
        except model.RuleBroken as problem:
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
        token = model.sign_up(self.db, data.get("name"), data.get("password"))
        self.send_me(201, model.current_user(self.db, token), cookie=token)

    def post_login(self, query):
        data = self.read_json()
        token = model.log_in(self.db, data.get("name"), data.get("password"))
        self.send_me(200, model.current_user(self.db, token), cookie=token)

    def post_logout(self, query):
        model.log_out(self.db, self.session_token())
        self.send_me(200, None, cookie="")

    def get_me(self, query):
        self.send_me(200, model.current_user(self.db, self.session_token()))

    def put_me(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        if "bio" in data:
            model.edit_profile(self.db, user["id"], data["bio"])
        if "avatar_id" in data:
            model.set_avatar(self.db, user["id"], data["avatar_id"])
        self.send_me(200, model.current_user(self.db, self.session_token()))

    def get_sidebar(self, query):
        viewer = model.current_user(self.db, self.session_token())
        viewer_id = viewer["id"] if viewer else None
        self.send_json(200, view.sidebar_to_json(model.trends(self.db), model.suggestions(self.db, viewer_id)))

    def get_search(self, query):
        post_ids, people = model.search(self.db, query.get("q", [""])[0])
        self.send_json(200, view.search_to_json(post_ids, people))

    def get_people(self, query):
        self.send_json(200, view.people_to_json(model.people(self.db)))

    # ---- Pictures ----

    def post_uploads(self, query):
        """The request's body is the picture itself, not JSON."""
        user = self.logged_in_user()
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            raise model.RuleBroken("The request must say how long the picture is.")
        # Read at most one byte more than allowed: enough for the model to see it is too big,
        # without filling the memory with a huge file.
        data = self.rfile.read(min(length, model.MAX_UPLOAD + 1))
        if length > model.MAX_UPLOAD + 1:
            self.close_connection = True   # the rest of the body was not read
        row = model.save_upload(self.db, user["id"], data)
        self.send_json(201, view.upload_to_json(row))

    def get_upload(self, query):
        file_name = urlparse(self.path).path[len("/uploads/"):]
        full_path, content_type = model.upload_file(self.db, file_name)
        with open(full_path, "rb") as file:
            body = file.read()
        self.send_answer(200, content_type, body, [
            # nosniff: the browser must treat it as the picture type we say, and nothing else.
            ("X-Content-Type-Options", "nosniff"),
            # Even opened on its own, the file may not load or run anything.
            ("Content-Security-Policy", "default-src 'none'"),
            # The name is random and never reused, so the browser may keep it for a year.
            ("Cache-Control", "public, max-age=31536000, immutable"),
        ])

    # ---- People ----

    def get_users(self, query):
        name = query.get("name", [""])[0]
        viewer = model.current_user(self.db, self.session_token())
        self.send_json(200, view.profile_to_json(model.profile(self.db, name, viewer["id"] if viewer else None)))

    def post_follows(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        model.follow(self.db, user["id"], data.get("name"))
        self.send_me(201, user)

    def delete_follows(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        model.unfollow(self.db, user["id"], data.get("name"))
        self.send_me(200, user)

    # ---- Posts ----

    def get_posts(self, query):
        try:
            after = int(query.get("after", ["0"])[0])
        except ValueError:
            raise model.RuleBroken("'after' must be a whole number.")
        self.send_json(200, view.posts_to_json(model.posts_after(self.db, after)))

    def post_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = model.save_post(self.db, user["id"], data.get("text"), data.get("reply_to"),
                              picture_id=data.get("picture_id"), quote_of=data.get("quote_of"))
        self.send_json(201, view.post_to_json(row))
        print(view.post_to_log_line(row), flush=True)   # one line in the terminal for each new post

    def put_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = model.edit_post(self.db, user["id"], data.get("post_id"), data.get("text"))
        self.send_json(200, view.post_to_json(row))

    def delete_posts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = model.delete_post(self.db, user["id"], data.get("post_id"))
        self.send_json(200, view.post_to_json(row))

    def post_reposts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(201, view.post_to_json(model.repost(self.db, user["id"], data.get("post_id"))))

    def delete_reposts(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(200, view.post_to_json(model.undo_repost(self.db, user["id"], data.get("post_id"))))

    def get_changes(self, query):
        self.send_json(200, view.posts_to_json(model.changed_posts(self.db)))

    # ---- Direct messages: always the logged-in person's own conversations ----

    def get_messages(self, query):
        user = self.logged_in_user()
        if "with" in query:
            person, rows = model.conversation(self.db, user["id"], query["with"][0])
            self.send_json(200, view.conversation_to_json(person, rows))
        else:
            self.send_json(200, view.conversations_to_json(model.conversations(self.db, user["id"])))

    def post_messages(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        row = model.send_message(self.db, user["id"], data.get("to"), data.get("text"))
        self.send_json(201, view.message_to_json(row))

    def post_messages_read(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        model.read_conversation(self.db, user["id"], data.get("with"))
        self.send_me(200, user)

    # ---- Notifications: always the logged-in person's own ----

    def get_notifications(self, query):
        user = self.logged_in_user()
        self.send_json(200, view.notifications_to_json(model.notifications_of(self.db, user["id"])))

    def post_notifications_read(self, query):
        user = self.logged_in_user()
        model.read_notifications(self.db, user["id"])
        self.send_me(200, user)

    # ---- Bookmarks: always the logged-in person's own ----

    def get_bookmarks(self, query):
        user = self.logged_in_user()
        self.send_json(200, view.bookmarks_to_json(model.bookmarks_of(self.db, user["id"])))

    def post_bookmarks(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(201, view.bookmarks_to_json(model.bookmark(self.db, user["id"], data.get("post_id"))))

    def delete_bookmarks(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(200, view.bookmarks_to_json(
            model.remove_bookmark(self.db, user["id"], data.get("post_id"))))

    # ---- Likes ----

    def get_likes(self, query):
        viewer = model.current_user(self.db, self.session_token())
        rows = model.like_counts(self.db, viewer["id"] if viewer else None)
        self.send_json(200, view.like_counts_to_json(rows))

    def post_likes(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(201, view.like_counts_to_json(model.like_post(self.db, user["id"], data.get("post_id"))))

    def delete_likes(self, query):
        user = self.logged_in_user()
        data = self.read_json()
        self.send_json(200, view.like_counts_to_json(model.unlike_post(self.db, user["id"], data.get("post_id"))))

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
            raise model.RuleBroken("The request must be JSON.")
        if not isinstance(data, dict):
            raise model.RuleBroken("The request must be a JSON object.")
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
        return model.user_for_token(self.db, self.session_token())

    # ---- Sending the answer ----

    def send_page(self, full_path):
        with open(full_path, "rb") as file:
            body = file.read()
        content_type = PAGE_TYPES[os.path.splitext(full_path)[1]]
        # no-cache: the browser checks for a newer file each time, so a change shows at once.
        self.send_answer(200, content_type, body, [("Cache-Control", "no-cache")])

    def send_me(self, status, user, cookie=None):
        """Send who is logged in (or nobody), and the names they follow."""
        following = model.followed_by(self.db, user["id"]) if user else []
        unread = model.unread_notifications(self.db, user["id"]) if user else 0
        messages = model.unread_messages(self.db, user["id"]) if user else 0
        self.send_json(status, view.me_to_json(user, following, unread, messages), cookie=cookie)

    def send_json(self, status, data, cookie=None):
        """Send data as JSON. With a cookie, also set the session cookie: a token logs the
        browser in, and "" logs it out."""
        headers = []
        if cookie is not None:
            # HttpOnly: the page's JavaScript cannot read it. SameSite=Strict: the browser sends it
            # only to this site, so another site cannot make your browser act as you.
            age = model.SESSION_DAYS * 24 * 60 * 60 if cookie else 0
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
                                                           "/users", "/events", "/people",
                                                           "/uploads", "/search", "/bookmarks",
                                                           "/notifications", "/sidebar",
                                                           "/messages")):
            return
        BaseHTTPRequestHandler.log_message(self, format, *args)


def page_file(path):
    """The file in page/ for this address, or None.

    "/" is page/index.html. An address that leads outside page/ (such as "/../model.py"),
    or to a type not in PAGE_TYPES, gets None, so model.py and timeline.db are never sent.
    """
    if path == "/":
        path = "/index.html"
    full = os.path.realpath(os.path.join(PAGE_DIR, path.lstrip("/")))
    if not full.startswith(PAGE_DIR + os.sep):
        return None
    if os.path.splitext(full)[1] not in PAGE_TYPES or not os.path.isfile(full):
        return None
    return full


ROUTES = {
    ("GET", "/events"): TimelineHandler.get_events,
    ("POST", "/signup"): TimelineHandler.post_signup,
    ("POST", "/login"): TimelineHandler.post_login,
    ("POST", "/logout"): TimelineHandler.post_logout,
    ("GET", "/me"): TimelineHandler.get_me,
    ("PUT", "/me"): TimelineHandler.put_me,
    ("GET", "/people"): TimelineHandler.get_people,
    ("GET", "/search"): TimelineHandler.get_search,
    ("GET", "/sidebar"): TimelineHandler.get_sidebar,
    ("POST", "/uploads"): TimelineHandler.post_uploads,
    ("GET", "/users"): TimelineHandler.get_users,
    ("POST", "/follows"): TimelineHandler.post_follows,
    ("DELETE", "/follows"): TimelineHandler.delete_follows,
    ("GET", "/posts"): TimelineHandler.get_posts,
    ("POST", "/posts"): TimelineHandler.post_posts,
    ("PUT", "/posts"): TimelineHandler.put_posts,
    ("DELETE", "/posts"): TimelineHandler.delete_posts,
    ("POST", "/reposts"): TimelineHandler.post_reposts,
    ("DELETE", "/reposts"): TimelineHandler.delete_reposts,
    ("GET", "/changes"): TimelineHandler.get_changes,
    ("GET", "/messages"): TimelineHandler.get_messages,
    ("POST", "/messages"): TimelineHandler.post_messages,
    ("POST", "/messages/read"): TimelineHandler.post_messages_read,
    ("GET", "/notifications"): TimelineHandler.get_notifications,
    ("POST", "/notifications/read"): TimelineHandler.post_notifications_read,
    ("GET", "/bookmarks"): TimelineHandler.get_bookmarks,
    ("POST", "/bookmarks"): TimelineHandler.post_bookmarks,
    ("DELETE", "/bookmarks"): TimelineHandler.delete_bookmarks,
    ("GET", "/likes"): TimelineHandler.get_likes,
    ("POST", "/likes"): TimelineHandler.post_likes,
    ("DELETE", "/likes"): TimelineHandler.delete_likes,
}


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
    model.create_tables(db_path)
    server = ThreadingHTTPServer(("127.0.0.1", port), TimelineHandler)
    server.db_path = db_path
    server.bell = Bell()
    return server


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Timeline server.")
    parser.add_argument("--port", type=int, default=8010)
    port = parser.parse_args().port
    server = make_server(port, model.DB_PATH)
    print("Timeline is running at http://localhost:" + str(port))
    print("The posts are kept in " + model.DB_PATH)
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    server.server_close()
