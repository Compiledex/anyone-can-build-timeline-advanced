"""Tests for server.py. Run them with:  python3 -m unittest

Most tests call the MODEL directly, with a database made only for the test.
The last tests start the real server and talk to it, as the page does.
"""

import http.cookiejar
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server

PASSWORD = "correct horse"


class ModelTests(unittest.TestCase):

    def setUp(self):
        # A new, empty database for every test, in a temporary folder.
        self.folder = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.folder.name, "test.db")
        server.create_tables(self.db_path)
        # Hashing a password is slow on purpose. The tests use fewer rounds, so they stay fast.
        self.rounds = server.PASSWORD_ROUNDS
        server.PASSWORD_ROUNDS = 1000

    def tearDown(self):
        server.PASSWORD_ROUNDS = self.rounds
        self.folder.cleanup()

    def user(self, name):
        """Sign up a person with this name, and return their user id."""
        token = server.sign_up(self.db_path, name, PASSWORD)
        return server.user_for_token(self.db_path, token)["id"]

    def query(self, sql):
        connection = server.connect(self.db_path)
        rows = connection.execute(sql).fetchall()
        connection.close()
        return rows

    # ---- Accounts ----

    def test_sign_up_logs_you_in(self):
        token = server.sign_up(self.db_path, " Aiko ", PASSWORD)
        self.assertEqual(server.user_for_token(self.db_path, token)["name"], "Aiko")

    def test_the_password_is_kept_only_as_a_hash(self):
        self.user("Aiko")
        stored = self.query("SELECT password_hash FROM users")[0]["password_hash"]
        self.assertNotIn(PASSWORD, stored)
        self.assertTrue(stored.startswith("pbkdf2_sha256$"))

    def test_the_same_password_gives_different_hashes(self):
        self.user("Aiko")
        self.user("Ben")
        hashes = [row["password_hash"] for row in self.query("SELECT password_hash FROM users")]
        self.assertNotEqual(hashes[0], hashes[1])  # each has its own random salt

    def test_a_short_password_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.sign_up(self.db_path, "Aiko", "1234567")

    def test_a_password_of_exactly_8_is_allowed(self):
        server.sign_up(self.db_path, "Aiko", "12345678")

    def test_an_empty_or_too_long_name_is_refused(self):
        for wrong in ["", "   ", "a" * 41, None]:
            with self.assertRaises(server.RuleBroken):
                server.sign_up(self.db_path, wrong, PASSWORD)

    def test_a_name_can_sign_up_only_once_whatever_its_capitals(self):
        self.user("Aiko")
        for same in ["Aiko", "aiko", " AIKO "]:
            with self.assertRaises(server.RuleBroken):
                server.sign_up(self.db_path, same, PASSWORD)

    def test_log_in_with_the_right_password(self):
        self.user("Aiko")
        token = server.log_in(self.db_path, "aiko", PASSWORD)
        self.assertEqual(server.user_for_token(self.db_path, token)["name"], "Aiko")

    def test_a_wrong_password_and_a_wrong_name_get_the_same_answer(self):
        self.user("Aiko")
        answers = []
        for name, password in [("Aiko", "wrong password"), ("Nobody", PASSWORD)]:
            with self.assertRaises(server.RuleBroken) as caught:
                server.log_in(self.db_path, name, password)
            answers.append(str(caught.exception))
        self.assertEqual(answers[0], answers[1])

    def test_log_out_ends_the_session(self):
        token = server.sign_up(self.db_path, "Aiko", PASSWORD)
        server.log_out(self.db_path, token)
        with self.assertRaises(server.NotLoggedIn):
            server.user_for_token(self.db_path, token)

    def test_a_made_up_or_empty_token_is_not_logged_in(self):
        self.user("Aiko")
        for wrong in ["made-up", "", None]:
            self.assertIsNone(server.current_user(self.db_path, wrong))
            with self.assertRaises(server.NotLoggedIn):
                server.user_for_token(self.db_path, wrong)

    def test_an_old_session_is_not_logged_in(self):
        token = server.sign_up(self.db_path, "Aiko", PASSWORD)
        connection = server.connect(self.db_path)
        connection.execute("UPDATE sessions SET expires_at = '2000-01-01 00:00'")
        connection.commit()
        connection.close()
        self.assertIsNone(server.current_user(self.db_path, token))

    def test_the_database_keeps_only_a_hash_of_the_token(self):
        token = server.sign_up(self.db_path, "Aiko", PASSWORD)
        stored = self.query("SELECT token_hash FROM sessions")[0]["token_hash"]
        self.assertNotEqual(stored, token)

    def test_an_old_database_without_accounts_is_refused(self):
        old_path = os.path.join(self.folder.name, "old.db")
        connection = sqlite3.connect(old_path)
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        connection.close()
        with self.assertRaises(SystemExit):
            server.create_tables(old_path)

    # ---- Posts ----

    def test_empty_text_is_refused(self):
        aiko = self.user("Aiko")
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, aiko, "   ")

    def test_too_long_text_is_refused(self):
        aiko = self.user("Aiko")
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, aiko, "a" * 281)

    def test_text_of_exactly_280_is_allowed(self):
        aiko = self.user("Aiko")
        row = server.save_post(self.db_path, aiko, "a" * 280)
        self.assertEqual(len(row["text"]), 280)

    def test_saved_post_comes_back_with_id_author_and_time(self):
        aiko = self.user("Aiko")
        row = server.save_post(self.db_path, aiko, " the library is open late ")
        self.assertEqual(row["id"], 1)
        self.assertEqual(row["author"], "Aiko")
        self.assertEqual(row["text"], "the library is open late")
        self.assertRegex(row["posted_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_a_post_points_at_its_author_by_id(self):
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "the library is open late tonight")
        post = self.query("SELECT * FROM posts")[0]
        self.assertEqual(post["author_id"], aiko)
        self.assertNotIn("author", post.keys())  # the name is kept once, in users

    def test_after_returns_only_newer_posts_oldest_first(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "first")
        server.save_post(self.db_path, ben, "second")
        server.save_post(self.db_path, aiko, "third")
        rows = server.posts_after(self.db_path, 1)
        self.assertEqual([row["text"] for row in rows], ["second", "third"])

    def test_log_line_has_the_time_the_author_and_the_text(self):
        aiko = self.user("Aiko")
        row = server.save_post(self.db_path, aiko, "the library is open late tonight")
        self.assertEqual(server.post_to_log_line(row),
                         row["posted_at"] + "  Aiko: the library is open late tonight")

    # ---- Likes ----

    def test_a_like_is_counted(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        rows = server.like_post(self.db_path, ben, 1)
        self.assertEqual(server.like_counts_to_json(rows),
                         [{"post_id": 1, "likes": 1, "you_liked": True}])

    def test_the_same_person_cannot_like_a_post_twice(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        server.like_post(self.db_path, ben, 1)
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, ben, 1)
        self.assertEqual(server.like_counts(self.db_path)[0]["likes"], 1)

    def test_the_database_itself_refuses_a_second_like(self):
        # Even code that skips the model cannot save the same like twice.
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "hello")
        connection = server.connect(self.db_path)
        connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        connection.close()

    def test_like_counts_are_per_post_and_per_viewer(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        server.save_post(self.db_path, aiko, "first")
        server.save_post(self.db_path, ben, "second")
        server.save_post(self.db_path, aiko, "third")
        server.like_post(self.db_path, ben, 1)
        server.like_post(self.db_path, ben, 3)
        server.like_post(self.db_path, chen, 3)
        self.assertEqual(server.like_counts_to_json(server.like_counts(self.db_path, chen)),
                         [{"post_id": 1, "likes": 1, "you_liked": False},
                          {"post_id": 3, "likes": 2, "you_liked": True}])
        nobody = server.like_counts_to_json(server.like_counts(self.db_path, None))
        self.assertEqual([count["you_liked"] for count in nobody], [False, False])

    def test_liking_a_missing_post_is_refused(self):
        ben = self.user("Ben")
        with self.assertRaises(server.NotFound):
            server.like_post(self.db_path, ben, 7)

    def test_post_id_must_be_a_whole_number(self):
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "hello")
        for wrong in ["1", 1.5, True, None]:
            with self.assertRaises(server.RuleBroken):
                server.like_post(self.db_path, aiko, wrong)

    def test_unlike_takes_the_like_back(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        server.like_post(self.db_path, ben, 1)
        self.assertEqual(server.unlike_post(self.db_path, ben, 1), [])

    def test_unlike_without_a_like_is_refused(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        server.like_post(self.db_path, aiko, 1)
        with self.assertRaises(server.RuleBroken):
            server.unlike_post(self.db_path, ben, 1)
        self.assertEqual(server.like_counts(self.db_path)[0]["likes"], 1)  # Aiko's like stays

    # ---- Replies ----

    def test_a_reply_points_at_its_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "the library is open late tonight")
        row = server.save_post(self.db_path, ben, "thanks!", 1)
        self.assertEqual(server.post_to_json(row)["reply_to"], 1)

    def test_a_reply_to_a_missing_post_is_refused(self):
        ben = self.user("Ben")
        with self.assertRaises(server.NotFound):
            server.save_post(self.db_path, ben, "thanks!", 7)
        self.assertEqual(server.posts_after(self.db_path, 0), [])  # nothing was saved

    def test_reply_to_must_be_a_whole_number(self):
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "hello")
        for wrong in ["1", 1.5, True]:
            with self.assertRaises(server.RuleBroken):
                server.save_post(self.db_path, aiko, "thanks!", wrong)

    # ---- Edit ----

    def test_the_author_can_edit_a_post(self):
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "the libary is open late")
        row = server.edit_post(self.db_path, aiko, 1, " the library is open late ")
        self.assertEqual(row["text"], "the library is open late")
        self.assertRegex(row["edited_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_someone_else_cannot_edit_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        with self.assertRaises(server.RuleBroken):
            server.edit_post(self.db_path, ben, 1, "goodbye")
        self.assertEqual(server.posts_after(self.db_path, 0)[0]["text"], "hello")

    def test_an_edit_follows_the_post_rules(self):
        aiko = self.user("Aiko")
        server.save_post(self.db_path, aiko, "hello")
        for wrong in ["   ", "a" * 281]:
            with self.assertRaises(server.RuleBroken):
                server.edit_post(self.db_path, aiko, 1, wrong)

    # ---- Delete ----

    def test_the_author_can_delete_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "the library is open late tonight")
        server.like_post(self.db_path, ben, 1)
        row = server.delete_post(self.db_path, aiko, 1)
        self.assertEqual(row["text"], "")                          # the words are gone
        self.assertIsNotNone(row["deleted_at"])
        self.assertEqual(server.like_counts(self.db_path), [])     # and so are its likes

    def test_someone_else_cannot_delete_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        with self.assertRaises(server.RuleBroken):
            server.delete_post(self.db_path, ben, 1)

    def test_replies_stay_when_their_post_is_deleted(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        server.save_post(self.db_path, ben, "hi Aiko!", 1)
        server.delete_post(self.db_path, aiko, 1)
        rows = server.posts_to_json(server.posts_after(self.db_path, 0))
        self.assertEqual([(r["id"], r["text"], r["reply_to"]) for r in rows],
                         [(1, "", None), (2, "hi Aiko!", 1)])

    def test_a_deleted_post_cannot_be_liked_edited_replied_to_or_deleted_again(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "hello")
        server.delete_post(self.db_path, aiko, 1)
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, ben, 1)
        with self.assertRaises(server.RuleBroken):
            server.edit_post(self.db_path, aiko, 1, "back again")
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, ben, "hi!", 1)
        with self.assertRaises(server.RuleBroken):
            server.delete_post(self.db_path, aiko, 1)

    def test_changed_posts_lists_only_edited_and_deleted_posts(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        server.save_post(self.db_path, aiko, "first")
        server.save_post(self.db_path, ben, "second")
        server.save_post(self.db_path, aiko, "third")
        server.edit_post(self.db_path, ben, 2, "second, edited")
        server.delete_post(self.db_path, aiko, 3)
        rows = server.changed_posts(self.db_path)
        self.assertEqual([(row["id"], row["text"]) for row in rows],
                         [(2, "second, edited"), (3, "")])


class RealServerTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.folder.name, "test.db")
        self.rounds = server.PASSWORD_ROUNDS
        server.PASSWORD_ROUNDS = 1000
        # Port 0 asks the computer for any free port.
        self.server = server.make_server(0, db_path)
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        server.PASSWORD_ROUNDS = self.rounds
        self.folder.cleanup()

    def browser(self):
        """A new browser window: it keeps its own cookies, as a real browser does."""
        return urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def send(self, browser, method, path, data=None):
        """Send a request as the page does. Return the status and the JSON answer."""
        request = urllib.request.Request(
            self.base + path, method=method,
            data=None if data is None else json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"})
        try:
            with browser.open(request) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def signed_up(self, name):
        browser = self.browser()
        status, _ = self.send(browser, "POST", "/signup", {"name": name, "password": PASSWORD})
        self.assertEqual(status, 201)
        return browser

    def test_sign_up_post_then_get(self):
        aiko = self.signed_up("Aiko")
        self.assertEqual(self.send(aiko, "GET", "/me"), (200, {"name": "Aiko"}))
        status, post = self.send(aiko, "POST", "/posts", {"text": "hello"})
        self.assertEqual((status, post["author"]), (201, "Aiko"))
        status, posts = self.send(self.browser(), "GET", "/posts?after=0")  # anyone can read
        self.assertEqual([(p["author"], p["text"]) for p in posts], [("Aiko", "hello")])

    def test_the_session_cookie_cannot_be_read_by_the_page(self):
        request = urllib.request.Request(
            self.base + "/signup", method="POST",
            data=json.dumps({"name": "Aiko", "password": PASSWORD}).encode("utf-8"))
        with urllib.request.urlopen(request) as answer:
            cookie = answer.headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)

    def test_without_logging_in_you_can_read_but_not_write(self):
        stranger = self.browser()
        self.assertEqual(self.send(stranger, "GET", "/me"), (200, {"name": None}))
        for method, path, data in [("POST", "/posts", {"text": "hello"}),
                                   ("POST", "/likes", {"post_id": 1}),
                                   ("PUT", "/posts", {"post_id": 1, "text": "hi"}),
                                   ("DELETE", "/posts", {"post_id": 1})]:
            status, answer = self.send(stranger, method, path, data)
            self.assertEqual(status, 401)
            self.assertIn("log in", answer["error"])

    def test_log_out_then_log_in(self):
        aiko = self.signed_up("Aiko")
        self.send(aiko, "POST", "/logout")
        self.assertEqual(self.send(aiko, "GET", "/me"), (200, {"name": None}))
        self.assertEqual(self.send(aiko, "POST", "/posts", {"text": "hello"})[0], 401)
        status, _ = self.send(aiko, "POST", "/login", {"name": "Aiko", "password": "wrong one"})
        self.assertEqual(status, 400)
        status, me = self.send(aiko, "POST", "/login", {"name": "Aiko", "password": PASSWORD})
        self.assertEqual((status, me), (200, {"name": "Aiko"}))

    def test_like_unlike_and_who_liked(self):
        aiko, ben = self.signed_up("Aiko"), self.signed_up("Ben")
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        status, counts = self.send(ben, "POST", "/likes", {"post_id": 1})
        self.assertEqual((status, counts), (201, [{"post_id": 1, "likes": 1, "you_liked": True}]))
        self.assertEqual(self.send(ben, "POST", "/likes", {"post_id": 1})[0], 400)
        self.assertEqual(self.send(aiko, "GET", "/likes")[1],
                         [{"post_id": 1, "likes": 1, "you_liked": False}])
        self.assertEqual(self.send(ben, "DELETE", "/likes", {"post_id": 1}), (200, []))

    def test_reply_edit_and_delete(self):
        aiko, ben = self.signed_up("Aiko"), self.signed_up("Ben")
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        status, reply = self.send(ben, "POST", "/posts", {"text": "hi!", "reply_to": 1})
        self.assertEqual((status, reply["reply_to"]), (201, 1))
        status, answer = self.send(aiko, "PUT", "/posts", {"post_id": 2, "text": "not yours"})
        self.assertEqual(status, 400)
        self.assertIn("your own", answer["error"])
        status, edited = self.send(ben, "PUT", "/posts", {"post_id": 2, "text": "hi Aiko!"})
        self.assertEqual((status, edited["text"]), (200, "hi Aiko!"))
        status, deleted = self.send(aiko, "DELETE", "/posts", {"post_id": 1})
        self.assertEqual((status, deleted["text"]), (200, ""))
        changes = self.send(aiko, "GET", "/changes")[1]
        self.assertEqual([(p["id"], p["text"]) for p in changes], [(1, ""), (2, "hi Aiko!")])

    def test_a_missing_post_gets_404(self):
        aiko = self.signed_up("Aiko")
        self.assertEqual(self.send(aiko, "POST", "/likes", {"post_id": 7})[0], 404)

    def test_empty_post_gets_400_and_a_reason(self):
        aiko = self.signed_up("Aiko")
        status, answer = self.send(aiko, "POST", "/posts", {"text": ""})
        self.assertEqual(status, 400)
        self.assertIn("empty", answer["error"])


if __name__ == "__main__":
    unittest.main()
