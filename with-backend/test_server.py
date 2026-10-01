"""Tests for server.py. Run them with:  python3 -m unittest

Most tests call the MODEL directly, with a database made only for the test.
The last test starts the real server and talks to it, as the page does.
"""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import server


class ModelTests(unittest.TestCase):

    def setUp(self):
        # A new, empty database for every test, in a temporary folder.
        self.folder = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.folder.name, "test.db")
        server.create_tables(self.db_path)

    def tearDown(self):
        self.folder.cleanup()

    def test_empty_text_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "Aiko", "   ")

    def test_too_long_text_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "Aiko", "a" * 281)

    def test_text_of_exactly_280_is_allowed(self):
        row = server.save_post(self.db_path, "Aiko", "a" * 280)
        self.assertEqual(len(row["text"]), 280)

    def test_empty_author_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "", "hello")

    def test_too_long_author_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "a" * 41, "hello")

    def test_saved_post_comes_back_with_id_and_time(self):
        row = server.save_post(self.db_path, " Aiko ", " the library is open late ")
        self.assertEqual(row["id"], 1)
        self.assertEqual(row["author"], "Aiko")
        self.assertEqual(row["text"], "the library is open late")
        self.assertRegex(row["posted_at"], r"^\d\d:\d\d$")

    def test_the_same_name_is_one_user(self):
        server.save_post(self.db_path, "Aiko", "first")
        server.save_post(self.db_path, "Aiko", "second")
        server.save_post(self.db_path, "Ben", "third")
        connection = server.connect(self.db_path)
        users = connection.execute("SELECT name FROM users ORDER BY id").fetchall()
        connection.close()
        self.assertEqual([u["name"] for u in users], ["Aiko", "Ben"])

    def test_a_post_points_at_its_author_by_id(self):
        server.save_post(self.db_path, "Aiko", "the library is open late tonight")
        connection = server.connect(self.db_path)
        post = connection.execute("SELECT * FROM posts").fetchone()
        user = connection.execute("SELECT * FROM users").fetchone()
        connection.close()
        self.assertEqual(post["author_id"], user["id"])
        self.assertNotIn("author", post.keys())  # the name is kept once, in users

    def test_after_returns_only_newer_posts_oldest_first(self):
        server.save_post(self.db_path, "Aiko", "first")
        server.save_post(self.db_path, "Ben", "second")
        server.save_post(self.db_path, "Aiko", "third")
        rows = server.posts_after(self.db_path, 1)
        self.assertEqual([row["text"] for row in rows], ["second", "third"])


    def test_log_line_has_the_time_the_author_and_the_text(self):
        row = server.save_post(self.db_path, "Aiko", "the library is open late tonight")
        self.assertEqual(server.post_to_log_line(row),
                         row["posted_at"] + "  Aiko: the library is open late tonight")


class RealServerTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.folder.name, "test.db")
        # Port 0 asks the computer for any free port.
        self.server = server.make_server(0, db_path)
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.folder.cleanup()

    def post(self, data):
        request = urllib.request.Request(
            self.base + "/posts",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        return urllib.request.urlopen(request)

    def test_post_then_get(self):
        answer = self.post({"author": "Aiko", "text": "hello"})
        self.assertEqual(answer.status, 201)
        with urllib.request.urlopen(self.base + "/posts?after=0") as answer:
            posts = json.loads(answer.read())
        self.assertEqual(len(posts), 1)
        self.assertEqual(posts[0]["author"], "Aiko")
        self.assertEqual(posts[0]["text"], "hello")

    def test_empty_post_gets_400_and_a_reason(self):
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post({"author": "Aiko", "text": ""})
        self.assertEqual(caught.exception.code, 400)
        reason = json.loads(caught.exception.read())["error"]
        self.assertIn("empty", reason)
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
