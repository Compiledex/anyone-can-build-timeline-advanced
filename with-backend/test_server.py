"""Tests for server.py. Run them with:  python3 -m unittest

Most tests call the MODEL directly, with a database made only for the test.
The last test starts the real server and talks to it, as the page does.
"""

import json
import os
import sqlite3
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

    def test_a_like_is_counted(self):
        server.save_post(self.db_path, "Aiko", "the library is open late tonight")
        rows = server.like_post(self.db_path, 1, " Ben ")
        self.assertEqual(server.like_counts_to_json(rows),
                         [{"post_id": 1, "likes": 1, "you_liked": True}])

    def test_the_same_name_cannot_like_a_post_twice(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Ben")
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, 1, "Ben")
        rows = server.like_counts(self.db_path, "Ben")
        self.assertEqual(server.like_counts_to_json(rows),
                         [{"post_id": 1, "likes": 1, "you_liked": True}])

    def test_the_database_itself_refuses_a_second_like(self):
        # Even code that skips the model cannot save the same like twice.
        server.save_post(self.db_path, "Aiko", "hello")
        connection = server.connect(self.db_path)
        connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        connection.close()

    def test_two_names_can_like_the_same_post(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Aiko")
        rows = server.like_post(self.db_path, 1, "Ben")
        self.assertEqual(rows[0]["likes"], 2)

    def test_like_counts_are_per_post(self):
        server.save_post(self.db_path, "Aiko", "first")
        server.save_post(self.db_path, "Ben", "second")
        server.save_post(self.db_path, "Aiko", "third")
        server.like_post(self.db_path, 1, "Ben")
        server.like_post(self.db_path, 3, "Ben")
        server.like_post(self.db_path, 3, "Chen")
        rows = server.like_counts(self.db_path, "Chen")
        self.assertEqual(server.like_counts_to_json(rows),
                         [{"post_id": 1, "likes": 1, "you_liked": False},
                          {"post_id": 3, "likes": 2, "you_liked": True}])

    def test_a_like_keeps_the_name_once_in_users(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Aiko")
        connection = server.connect(self.db_path)
        users = connection.execute("SELECT name FROM users").fetchall()
        like = connection.execute("SELECT * FROM likes").fetchone()
        connection.close()
        self.assertEqual([u["name"] for u in users], ["Aiko"])
        self.assertEqual(like.keys(), ["post_id", "user_id"])  # ids only, no name, no count

    def test_liking_a_missing_post_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, 7, "Ben")

    def test_liking_with_an_empty_name_is_refused(self):
        server.save_post(self.db_path, "Aiko", "hello")
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, 1, "  ")

    def test_post_id_must_be_a_whole_number(self):
        server.save_post(self.db_path, "Aiko", "hello")
        for wrong in ["1", 1.5, True, None]:
            with self.assertRaises(server.RuleBroken):
                server.like_post(self.db_path, wrong, "Ben")

    # ---- Unlike ----

    def test_unlike_takes_the_like_back(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Ben")
        rows = server.unlike_post(self.db_path, 1, "Ben")
        self.assertEqual(rows, [])  # no post has a like any more

    def test_unlike_without_a_like_is_refused(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Aiko")
        with self.assertRaises(server.RuleBroken):
            server.unlike_post(self.db_path, 1, "Ben")
        self.assertEqual(server.like_counts(self.db_path)[0]["likes"], 1)  # Aiko's like stays

    def test_like_again_after_unlike(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.like_post(self.db_path, 1, "Ben")
        server.unlike_post(self.db_path, 1, "Ben")
        rows = server.like_post(self.db_path, 1, "Ben")
        self.assertEqual(rows[0]["likes"], 1)

    # ---- Replies ----

    def test_a_reply_points_at_its_post(self):
        server.save_post(self.db_path, "Aiko", "the library is open late tonight")
        row = server.save_post(self.db_path, "Ben", "thanks!", 1)
        self.assertEqual(server.post_to_json(row)["reply_to"], 1)

    def test_a_new_post_is_not_a_reply(self):
        row = server.save_post(self.db_path, "Aiko", "hello")
        self.assertIsNone(server.post_to_json(row)["reply_to"])

    def test_a_reply_to_a_missing_post_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "Ben", "thanks!", 7)
        self.assertEqual(server.posts_after(self.db_path, 0), [])  # nothing was saved

    def test_reply_to_must_be_a_whole_number(self):
        server.save_post(self.db_path, "Aiko", "hello")
        for wrong in ["1", 1.5, True]:
            with self.assertRaises(server.RuleBroken):
                server.save_post(self.db_path, "Ben", "thanks!", wrong)

    def test_a_reply_follows_the_post_rules(self):
        server.save_post(self.db_path, "Aiko", "hello")
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "Ben", "  ", 1)

    # ---- Edit ----

    def test_the_author_can_edit_a_post(self):
        server.save_post(self.db_path, "Aiko", "the libary is open late")
        row = server.edit_post(self.db_path, 1, " Aiko ", " the library is open late ")
        self.assertEqual(row["text"], "the library is open late")
        self.assertEqual(row["author"], "Aiko")
        self.assertRegex(row["edited_at"], r"^\d\d:\d\d$")

    def test_someone_else_cannot_edit_a_post(self):
        server.save_post(self.db_path, "Aiko", "hello")
        with self.assertRaises(server.RuleBroken):
            server.edit_post(self.db_path, 1, "Ben", "goodbye")
        self.assertEqual(server.posts_after(self.db_path, 0)[0]["text"], "hello")

    def test_an_edit_follows_the_post_rules(self):
        server.save_post(self.db_path, "Aiko", "hello")
        for wrong in ["   ", "a" * 281]:
            with self.assertRaises(server.RuleBroken):
                server.edit_post(self.db_path, 1, "Aiko", wrong)

    def test_editing_a_missing_post_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.edit_post(self.db_path, 7, "Aiko", "hello")

    def test_changed_posts_lists_only_edited_and_deleted_posts(self):
        server.save_post(self.db_path, "Aiko", "first")
        server.save_post(self.db_path, "Ben", "second")
        server.save_post(self.db_path, "Aiko", "third")
        server.edit_post(self.db_path, 2, "Ben", "second, edited")
        server.delete_post(self.db_path, 3, "Aiko")
        rows = server.changed_posts(self.db_path)
        self.assertEqual([(row["id"], row["text"]) for row in rows],
                         [(2, "second, edited"), (3, "")])

    # ---- Delete ----

    def test_the_author_can_delete_a_post(self):
        server.save_post(self.db_path, "Aiko", "the library is open late tonight")
        server.like_post(self.db_path, 1, "Ben")
        row = server.delete_post(self.db_path, 1, " Aiko ")
        self.assertEqual(row["text"], "")                          # the words are gone
        self.assertRegex(row["deleted_at"], r"^\d\d:\d\d$")
        self.assertEqual(server.like_counts(self.db_path), [])     # and so are its likes

    def test_someone_else_cannot_delete_a_post(self):
        server.save_post(self.db_path, "Aiko", "hello")
        with self.assertRaises(server.RuleBroken):
            server.delete_post(self.db_path, 1, "Ben")
        self.assertEqual(server.posts_after(self.db_path, 0)[0]["text"], "hello")

    def test_deleting_twice_is_refused(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.delete_post(self.db_path, 1, "Aiko")
        with self.assertRaises(server.RuleBroken):
            server.delete_post(self.db_path, 1, "Aiko")

    def test_deleting_a_missing_post_is_refused(self):
        with self.assertRaises(server.RuleBroken):
            server.delete_post(self.db_path, 7, "Aiko")

    def test_replies_stay_when_their_post_is_deleted(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.save_post(self.db_path, "Ben", "hi Aiko!", 1)
        server.delete_post(self.db_path, 1, "Aiko")
        rows = server.posts_to_json(server.posts_after(self.db_path, 0))
        self.assertEqual([(r["id"], r["text"], r["reply_to"]) for r in rows],
                         [(1, "", None), (2, "hi Aiko!", 1)])

    def test_a_reply_can_be_deleted_by_its_author(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.save_post(self.db_path, "Ben", "hi Aiko!", 1)
        row = server.delete_post(self.db_path, 2, "Ben")
        self.assertEqual((row["text"], row["reply_to"]), ("", 1))

    def test_a_deleted_post_cannot_be_liked_edited_or_replied_to(self):
        server.save_post(self.db_path, "Aiko", "hello")
        server.delete_post(self.db_path, 1, "Aiko")
        with self.assertRaises(server.RuleBroken):
            server.like_post(self.db_path, 1, "Ben")
        with self.assertRaises(server.RuleBroken):
            server.edit_post(self.db_path, 1, "Aiko", "back again")
        with self.assertRaises(server.RuleBroken):
            server.save_post(self.db_path, "Ben", "hi!", 1)

    def test_an_old_database_gets_the_new_columns_and_keeps_its_posts(self):
        # A timeline.db made before replies, edits and deleting existed.
        old_path = os.path.join(self.folder.name, "old.db")
        connection = sqlite3.connect(old_path)
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        connection.execute("CREATE TABLE posts (id INTEGER PRIMARY KEY, "
                           "author_id INTEGER NOT NULL REFERENCES users(id), "
                           "text TEXT NOT NULL, posted_at TEXT NOT NULL)")
        connection.execute("INSERT INTO users (name) VALUES ('Aiko')")
        connection.execute("INSERT INTO posts (author_id, text, posted_at) VALUES (1, 'hello', '15:20')")
        connection.commit()
        connection.close()
        server.create_tables(old_path)
        server.save_post(old_path, "Ben", "hi!", 1)
        server.delete_post(old_path, 2, "Ben")
        rows = server.posts_to_json(server.posts_after(old_path, 0))
        self.assertEqual([(r["text"], r["reply_to"]) for r in rows], [("hello", None), ("", 1)])


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

    def post(self, data, path="/posts", method="POST"):
        request = urllib.request.Request(
            self.base + path,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method=method,
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

    def test_like_then_get_likes(self):
        self.post({"author": "Aiko", "text": "hello"}).close()
        with self.post({"post_id": 1, "name": "Ben"}, "/likes") as answer:
            self.assertEqual(answer.status, 201)
            self.assertEqual(json.loads(answer.read()),
                             [{"post_id": 1, "likes": 1, "you_liked": True}])
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post({"post_id": 1, "name": "Ben"}, "/likes")
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("already", json.loads(caught.exception.read())["error"])
        caught.exception.close()
        with urllib.request.urlopen(self.base + "/likes?name=Ben") as answer:
            self.assertEqual(json.loads(answer.read()),
                             [{"post_id": 1, "likes": 1, "you_liked": True}])
        with urllib.request.urlopen(self.base + "/likes?name=Aiko") as answer:
            self.assertEqual(json.loads(answer.read()),
                             [{"post_id": 1, "likes": 1, "you_liked": False}])

    def test_reply_edit_and_unlike(self):
        self.post({"author": "Aiko", "text": "hello"}).close()
        with self.post({"author": "Ben", "text": "hi!", "reply_to": 1}) as answer:
            self.assertEqual(json.loads(answer.read())["reply_to"], 1)
        with self.post({"post_id": 2, "name": "Ben", "text": "hi Aiko!"}, method="PUT") as answer:
            self.assertEqual(answer.status, 200)
            self.assertEqual(json.loads(answer.read())["text"], "hi Aiko!")
        with urllib.request.urlopen(self.base + "/changes") as answer:
            self.assertEqual([p["id"] for p in json.loads(answer.read())], [2])
        self.post({"post_id": 1, "name": "Ben"}, "/likes").close()
        with self.post({"post_id": 1, "name": "Ben"}, "/likes", method="DELETE") as answer:
            self.assertEqual(answer.status, 200)
            self.assertEqual(json.loads(answer.read()), [])

    def test_delete_over_http(self):
        self.post({"author": "Aiko", "text": "hello"}).close()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post({"post_id": 1, "name": "Ben"}, method="DELETE")
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("your own", json.loads(caught.exception.read())["error"])
        caught.exception.close()
        with self.post({"post_id": 1, "name": "Aiko"}, method="DELETE") as answer:
            self.assertEqual(answer.status, 200)
            self.assertEqual(json.loads(answer.read())["text"], "")
        with urllib.request.urlopen(self.base + "/changes") as answer:
            post = json.loads(answer.read())[0]
        self.assertEqual((post["id"], post["text"]), (1, ""))
        self.assertIsNotNone(post["deleted_at"])

    def test_editing_someone_elses_post_gets_400(self):
        self.post({"author": "Aiko", "text": "hello"}).close()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            self.post({"post_id": 1, "name": "Ben", "text": "goodbye"}, method="PUT")
        self.assertEqual(caught.exception.code, 400)
        self.assertIn("your own", json.loads(caught.exception.read())["error"])
        caught.exception.close()


if __name__ == "__main__":
    unittest.main()
