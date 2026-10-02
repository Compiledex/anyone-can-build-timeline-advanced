"""Tests for the backend (server.py, model.py, view.py) and seed.py. Run them with:  python3 -m unittest

Most tests call the MODEL directly, with a database made only for the test.
The last tests start the real server and talk to it, as the page does.
"""

import http.client
import http.cookiejar
import json
import os
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request

import model
import seed
import server
import view

PASSWORD = "correct horse"


class ModelTests(unittest.TestCase):

    def setUp(self):
        # A new, empty database for every test, in a temporary folder.
        self.folder = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.folder.name, "test.db")
        model.create_tables(self.db_path)
        # Hashing a password is slow on purpose. The tests use fewer rounds, so they stay fast.
        self.rounds = model.PASSWORD_ROUNDS
        model.PASSWORD_ROUNDS = 1000

    def tearDown(self):
        model.PASSWORD_ROUNDS = self.rounds
        self.folder.cleanup()

    def user(self, name):
        """Sign up a person with this name, and return their user id."""
        token = model.sign_up(self.db_path, name, PASSWORD)
        return model.user_for_token(self.db_path, token)["id"]

    def query(self, sql):
        connection = model.connect(self.db_path)
        rows = connection.execute(sql).fetchall()
        connection.close()
        return rows

    # ---- Accounts ----

    def test_sign_up_logs_you_in(self):
        token = model.sign_up(self.db_path, " Aiko ", PASSWORD)
        self.assertEqual(model.user_for_token(self.db_path, token)["name"], "Aiko")

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
        with self.assertRaises(model.RuleBroken):
            model.sign_up(self.db_path, "Aiko", "1234567")

    def test_a_password_of_exactly_8_is_allowed(self):
        model.sign_up(self.db_path, "Aiko", "12345678")

    def test_an_empty_or_too_long_name_is_refused(self):
        for wrong in ["", "   ", "a" * 41, None]:
            with self.assertRaises(model.RuleBroken):
                model.sign_up(self.db_path, wrong, PASSWORD)

    def test_a_name_can_sign_up_only_once_whatever_its_capitals(self):
        self.user("Aiko")
        for same in ["Aiko", "aiko", " AIKO "]:
            with self.assertRaises(model.RuleBroken):
                model.sign_up(self.db_path, same, PASSWORD)

    def test_log_in_with_the_right_password(self):
        self.user("Aiko")
        token = model.log_in(self.db_path, "aiko", PASSWORD)
        self.assertEqual(model.user_for_token(self.db_path, token)["name"], "Aiko")

    def test_a_wrong_password_and_a_wrong_name_get_the_same_answer(self):
        self.user("Aiko")
        answers = []
        for name, password in [("Aiko", "wrong password"), ("Nobody", PASSWORD)]:
            with self.assertRaises(model.RuleBroken) as caught:
                model.log_in(self.db_path, name, password)
            answers.append(str(caught.exception))
        self.assertEqual(answers[0], answers[1])

    def test_log_out_ends_the_session(self):
        token = model.sign_up(self.db_path, "Aiko", PASSWORD)
        model.log_out(self.db_path, token)
        with self.assertRaises(model.NotLoggedIn):
            model.user_for_token(self.db_path, token)

    def test_a_made_up_or_empty_token_is_not_logged_in(self):
        self.user("Aiko")
        for wrong in ["made-up", "", None]:
            self.assertIsNone(model.current_user(self.db_path, wrong))
            with self.assertRaises(model.NotLoggedIn):
                model.user_for_token(self.db_path, wrong)

    def test_an_old_session_is_not_logged_in(self):
        token = model.sign_up(self.db_path, "Aiko", PASSWORD)
        connection = model.connect(self.db_path)
        connection.execute("UPDATE sessions SET expires_at = '2000-01-01 00:00'")
        connection.commit()
        connection.close()
        self.assertIsNone(model.current_user(self.db_path, token))

    def test_the_database_keeps_only_a_hash_of_the_token(self):
        token = model.sign_up(self.db_path, "Aiko", PASSWORD)
        stored = self.query("SELECT token_hash FROM sessions")[0]["token_hash"]
        self.assertNotEqual(stored, token)

    def test_an_old_database_without_accounts_is_refused(self):
        old_path = os.path.join(self.folder.name, "old.db")
        connection = sqlite3.connect(old_path)
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE)")
        connection.close()
        with self.assertRaises(SystemExit):
            model.create_tables(old_path)

    # ---- Posts ----

    def test_empty_text_is_refused(self):
        aiko = self.user("Aiko")
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, aiko, "   ")

    def test_too_long_text_is_refused(self):
        aiko = self.user("Aiko")
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, aiko, "a" * 281)

    def test_text_of_exactly_280_is_allowed(self):
        aiko = self.user("Aiko")
        row = model.save_post(self.db_path, aiko, "a" * 280)
        self.assertEqual(len(row["text"]), 280)

    def test_saved_post_comes_back_with_id_author_and_time(self):
        aiko = self.user("Aiko")
        row = model.save_post(self.db_path, aiko, " the library is open late ")
        self.assertEqual(row["id"], 1)
        self.assertEqual(row["author"], "Aiko")
        self.assertEqual(row["text"], "the library is open late")
        self.assertRegex(row["posted_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_a_post_points_at_its_author_by_id(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "the library is open late tonight")
        post = self.query("SELECT * FROM posts")[0]
        self.assertEqual(post["author_id"], aiko)
        self.assertNotIn("author", post.keys())  # the name is kept once, in users

    def test_after_returns_only_newer_posts_oldest_first(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "first")
        model.save_post(self.db_path, ben, "second")
        model.save_post(self.db_path, aiko, "third")
        rows = model.posts_after(self.db_path, 1)
        self.assertEqual([row["text"] for row in rows], ["second", "third"])

    def test_log_line_has_the_time_the_author_and_the_text(self):
        aiko = self.user("Aiko")
        row = model.save_post(self.db_path, aiko, "the library is open late tonight")
        self.assertEqual(view.post_to_log_line(row),
                         row["posted_at"] + "  Aiko: the library is open late tonight")

    # ---- Likes ----

    def test_a_like_is_counted(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        rows = model.like_post(self.db_path, ben, 1)
        self.assertEqual(view.like_counts_to_json(rows),
                         [{"post_id": 1, "likes": 1, "you_liked": True}])

    def test_the_same_person_cannot_like_a_post_twice(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.like_post(self.db_path, ben, 1)
        with self.assertRaises(model.RuleBroken):
            model.like_post(self.db_path, ben, 1)
        self.assertEqual(model.like_counts(self.db_path)[0]["likes"], 1)

    def test_the_database_itself_refuses_a_second_like(self):
        # Even code that skips the model cannot save the same like twice.
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        connection = model.connect(self.db_path)
        connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO likes (post_id, user_id) VALUES (1, 1)")
        connection.close()

    def test_like_counts_are_per_post_and_per_viewer(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.save_post(self.db_path, aiko, "first")
        model.save_post(self.db_path, ben, "second")
        model.save_post(self.db_path, aiko, "third")
        model.like_post(self.db_path, ben, 1)
        model.like_post(self.db_path, ben, 3)
        model.like_post(self.db_path, chen, 3)
        self.assertEqual(view.like_counts_to_json(model.like_counts(self.db_path, chen)),
                         [{"post_id": 1, "likes": 1, "you_liked": False},
                          {"post_id": 3, "likes": 2, "you_liked": True}])
        nobody = view.like_counts_to_json(model.like_counts(self.db_path, None))
        self.assertEqual([count["you_liked"] for count in nobody], [False, False])

    def test_liking_a_missing_post_is_refused(self):
        ben = self.user("Ben")
        with self.assertRaises(model.NotFound):
            model.like_post(self.db_path, ben, 7)

    def test_post_id_must_be_a_whole_number(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        for wrong in ["1", 1.5, True, None]:
            with self.assertRaises(model.RuleBroken):
                model.like_post(self.db_path, aiko, wrong)

    def test_unlike_takes_the_like_back(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.like_post(self.db_path, ben, 1)
        self.assertEqual(model.unlike_post(self.db_path, ben, 1), [])

    def test_unlike_without_a_like_is_refused(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.like_post(self.db_path, aiko, 1)
        with self.assertRaises(model.RuleBroken):
            model.unlike_post(self.db_path, ben, 1)
        self.assertEqual(model.like_counts(self.db_path)[0]["likes"], 1)  # Aiko's like stays

    # ---- Replies ----

    def test_a_reply_points_at_its_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "the library is open late tonight")
        row = model.save_post(self.db_path, ben, "thanks!", 1)
        self.assertEqual(view.post_to_json(row)["reply_to"], 1)

    def test_a_reply_to_a_missing_post_is_refused(self):
        ben = self.user("Ben")
        with self.assertRaises(model.NotFound):
            model.save_post(self.db_path, ben, "thanks!", 7)
        self.assertEqual(model.posts_after(self.db_path, 0), [])  # nothing was saved

    def test_reply_to_must_be_a_whole_number(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        for wrong in ["1", 1.5, True]:
            with self.assertRaises(model.RuleBroken):
                model.save_post(self.db_path, aiko, "thanks!", wrong)

    # ---- Edit ----

    def test_the_author_can_edit_a_post(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "the libary is open late")
        row = model.edit_post(self.db_path, aiko, 1, " the library is open late ")
        self.assertEqual(row["text"], "the library is open late")
        self.assertRegex(row["edited_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_someone_else_cannot_edit_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        with self.assertRaises(model.RuleBroken):
            model.edit_post(self.db_path, ben, 1, "goodbye")
        self.assertEqual(model.posts_after(self.db_path, 0)[0]["text"], "hello")

    def test_an_edit_follows_the_post_rules(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        for wrong in ["   ", "a" * 281]:
            with self.assertRaises(model.RuleBroken):
                model.edit_post(self.db_path, aiko, 1, wrong)

    # ---- Delete ----

    def test_the_author_can_delete_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "the library is open late tonight")
        model.like_post(self.db_path, ben, 1)
        row = model.delete_post(self.db_path, aiko, 1)
        self.assertEqual(row["text"], "")                          # the words are gone
        self.assertIsNotNone(row["deleted_at"])
        self.assertEqual(model.like_counts(self.db_path), [])     # and so are its likes

    def test_someone_else_cannot_delete_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        with self.assertRaises(model.RuleBroken):
            model.delete_post(self.db_path, ben, 1)

    def test_replies_stay_when_their_post_is_deleted(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.save_post(self.db_path, ben, "hi Aiko!", 1)
        model.delete_post(self.db_path, aiko, 1)
        rows = view.posts_to_json(model.posts_after(self.db_path, 0))
        self.assertEqual([(r["id"], r["text"], r["reply_to"]) for r in rows],
                         [(1, "", None), (2, "hi Aiko!", 1)])

    def test_a_deleted_post_cannot_be_liked_edited_replied_to_or_deleted_again(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.delete_post(self.db_path, aiko, 1)
        with self.assertRaises(model.RuleBroken):
            model.like_post(self.db_path, ben, 1)
        with self.assertRaises(model.RuleBroken):
            model.edit_post(self.db_path, aiko, 1, "back again")
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, ben, "hi!", 1)
        with self.assertRaises(model.RuleBroken):
            model.delete_post(self.db_path, aiko, 1)

    def test_changed_posts_lists_only_edited_and_deleted_posts(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "first")
        model.save_post(self.db_path, ben, "second")
        model.save_post(self.db_path, aiko, "third")
        model.edit_post(self.db_path, ben, 2, "second, edited")
        model.delete_post(self.db_path, aiko, 3)
        rows = model.changed_posts(self.db_path)
        self.assertEqual([(row["id"], row["text"]) for row in rows],
                         [(2, "second, edited"), (3, "")])


    # ---- Profiles ----

    def test_a_profile_has_the_name_join_time_and_posts(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "first")
        model.save_post(self.db_path, aiko, "second")
        model.delete_post(self.db_path, aiko, 2)
        row = model.profile(self.db_path, " aiko ")   # any capitals find the person
        self.assertEqual((row["name"], row["posts"]), ("Aiko", 1))   # a deleted post does not count
        self.assertRegex(row["joined_at"], r"^\d{4}-\d\d-\d\d \d\d:\d\d$")

    def test_a_profile_of_nobody_is_not_found(self):
        for wrong in ["Nobody", "", None]:
            with self.assertRaises(model.NotFound):
                model.profile(self.db_path, wrong)

    # ---- Follows ----

    def test_follow_someone(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        self.user("Chen")
        model.follow(self.db_path, aiko, "chen")
        model.follow(self.db_path, aiko, "Ben")
        self.assertEqual([row["name"] for row in model.followed_by(self.db_path, aiko)],
                         ["Ben", "Chen"])
        self.assertEqual(model.followed_by(self.db_path, ben), [])   # following is one way

    def test_you_cannot_follow_yourself(self):
        aiko = self.user("Aiko")
        with self.assertRaises(model.RuleBroken):
            model.follow(self.db_path, aiko, "Aiko")

    def test_the_database_itself_refuses_following_yourself(self):
        self.user("Aiko")
        connection = model.connect(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO follows (follower_id, followed_id) VALUES (1, 1)")
        connection.close()

    def test_you_cannot_follow_someone_twice(self):
        aiko = self.user("Aiko")
        self.user("Ben")
        model.follow(self.db_path, aiko, "Ben")
        with self.assertRaises(model.RuleBroken):
            model.follow(self.db_path, aiko, "BEN")

    def test_unfollow(self):
        aiko = self.user("Aiko")
        self.user("Ben")
        model.follow(self.db_path, aiko, "Ben")
        model.unfollow(self.db_path, aiko, "Ben")
        self.assertEqual(model.followed_by(self.db_path, aiko), [])
        with self.assertRaises(model.RuleBroken):
            model.unfollow(self.db_path, aiko, "Ben")   # not following any more

    def test_following_nobody_is_not_found(self):
        aiko = self.user("Aiko")
        with self.assertRaises(model.NotFound):
            model.follow(self.db_path, aiko, "Nobody")

    def test_a_profile_counts_followers_and_following(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.follow(self.db_path, aiko, "Ben")
        model.follow(self.db_path, chen, "Ben")
        model.follow(self.db_path, ben, "Aiko")
        row = view.profile_to_json(model.profile(self.db_path, "Ben", aiko))
        self.assertEqual((row["followers"], row["following"], row["you_follow"]), (2, 1, True))
        row = view.profile_to_json(model.profile(self.db_path, "Ben", None))
        self.assertFalse(row["you_follow"])

    # ---- Edit profile ----

    def test_edit_your_bio(self):
        aiko = self.user("Aiko")
        model.edit_profile(self.db_path, aiko, "  Exchange student from Osaka. 🍁 ")
        self.assertEqual(model.profile(self.db_path, "Aiko")["bio"], "Exchange student from Osaka. 🍁")
        model.edit_profile(self.db_path, aiko, "")
        self.assertEqual(model.profile(self.db_path, "Aiko")["bio"], "")   # an empty bio is allowed

    def test_a_too_long_bio_is_refused(self):
        aiko = self.user("Aiko")
        model.edit_profile(self.db_path, aiko, "a" * 160)
        with self.assertRaises(model.RuleBroken):
            model.edit_profile(self.db_path, aiko, "a" * 161)

    def test_an_older_database_gets_the_bio_column(self):
        old_path = os.path.join(self.folder.name, "old.db")
        connection = sqlite3.connect(old_path)
        connection.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL UNIQUE "
                           "COLLATE NOCASE, password_hash TEXT NOT NULL, joined_at TEXT NOT NULL)")
        connection.execute("INSERT INTO users (name, password_hash, joined_at) VALUES ('Aiko', 'x$1$00$00', '2026-10-01 10:00')")
        connection.commit()
        connection.close()
        model.create_tables(old_path)
        self.assertEqual(model.profile(old_path, "Aiko")["bio"], "")   # Aiko is still there

    # ---- Pictures ----

    PNG = b"\x89PNG\r\n\x1a\n" + b"made-up picture bytes"

    def test_upload_a_picture(self):
        aiko = self.user("Aiko")
        row = model.save_upload(self.db_path, aiko, self.PNG)
        self.assertTrue(row["file_name"].endswith(".png"))
        self.assertEqual(row["content_type"], "image/png")
        full_path, _ = model.upload_file(self.db_path, row["file_name"])
        with open(full_path, "rb") as file:
            self.assertEqual(file.read(), self.PNG)

    def test_each_picture_type_is_known_by_its_first_bytes(self):
        aiko = self.user("Aiko")
        for data, ending in [(b"\xff\xd8\xff\xe0 jpeg", ".jpg"), (b"GIF89a gif", ".gif"),
                             (b"RIFF\x00\x00\x00\x00WEBPVP8 ", ".webp")]:
            self.assertTrue(model.save_upload(self.db_path, aiko, data)["file_name"].endswith(ending))

    def test_anything_that_is_not_a_picture_is_refused(self):
        aiko = self.user("Aiko")
        for data in [b"", b"just some text", b"<svg xmlns='http://www.w3.org/2000/svg'><script/></svg>",
                     b"<html><script>alert(1)</script></html>"]:
            with self.assertRaises(model.RuleBroken):
                model.save_upload(self.db_path, aiko, data)

    def test_a_picture_over_2_mb_is_refused(self):
        aiko = self.user("Aiko")
        model.save_upload(self.db_path, aiko, self.PNG.ljust(model.MAX_UPLOAD, b"x"))
        with self.assertRaises(model.RuleBroken):
            model.save_upload(self.db_path, aiko, self.PNG.ljust(model.MAX_UPLOAD + 1, b"x"))

    def test_a_post_with_a_picture_and_no_text(self):
        aiko = self.user("Aiko")
        upload = model.save_upload(self.db_path, aiko, self.PNG)
        row = view.post_to_json(model.save_post(self.db_path, aiko, "", picture_id=upload["id"]))
        self.assertEqual(row["picture"], "/uploads/" + upload["file_name"])
        self.assertEqual(row["text"], "")

    def test_a_picture_is_used_once_and_only_by_its_owner(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        upload = model.save_upload(self.db_path, aiko, self.PNG)
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, ben, "mine now", picture_id=upload["id"])
        model.save_post(self.db_path, aiko, "first", picture_id=upload["id"])
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, aiko, "again", picture_id=upload["id"])
        with self.assertRaises(model.RuleBroken):
            model.set_avatar(self.db_path, aiko, upload["id"])

    def test_deleting_a_post_deletes_its_picture(self):
        aiko = self.user("Aiko")
        upload = model.save_upload(self.db_path, aiko, self.PNG)
        model.save_post(self.db_path, aiko, "look", picture_id=upload["id"])
        full_path, _ = model.upload_file(self.db_path, upload["file_name"])
        model.delete_post(self.db_path, aiko, 1)
        self.assertFalse(os.path.exists(full_path))
        with self.assertRaises(model.NotFound):
            model.upload_file(self.db_path, upload["file_name"])

    def test_a_profile_picture(self):
        aiko = self.user("Aiko")
        first = model.save_upload(self.db_path, aiko, self.PNG)
        model.set_avatar(self.db_path, aiko, first["id"])
        self.assertEqual(view.profile_to_json(model.profile(self.db_path, "Aiko"))["avatar"],
                         "/uploads/" + first["file_name"])
        second = model.save_upload(self.db_path, aiko, self.PNG)
        model.set_avatar(self.db_path, aiko, second["id"])          # the old picture is deleted
        with self.assertRaises(model.NotFound):
            model.upload_file(self.db_path, first["file_name"])
        model.set_avatar(self.db_path, aiko, None)                  # no picture: the first letter again
        self.assertEqual(view.people_to_json(model.people(self.db_path)), [{"name": "Aiko", "avatar": None}])

    def test_only_saved_names_are_ever_opened(self):
        for wrong in ["../timeline.db", "../model.py", "nothing.png", ""]:
            with self.assertRaises(model.NotFound):
                model.upload_file(self.db_path, wrong)

    # ---- Reposts and quotes ----

    def test_repost(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        row = view.post_to_json(model.repost(self.db_path, ben, 1))
        self.assertEqual((row["author"], row["repost_of"], row["text"]), ("Ben", 1, ""))

    def test_you_cannot_repost_a_post_twice(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.repost(self.db_path, ben, 1)
        with self.assertRaises(model.RuleBroken):
            model.repost(self.db_path, ben, 1)
        with self.assertRaises(model.RuleBroken):
            model.repost(self.db_path, ben, 2)   # reposting the repost reposts the original

    def test_the_database_itself_refuses_a_second_repost(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        connection = model.connect(self.db_path)
        insert = "INSERT INTO posts (author_id, text, posted_at, repost_of) VALUES (1, '', 'now', 1)"
        connection.execute(insert)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute(insert)
        connection.close()

    def test_undo_a_repost_then_repost_again(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.repost(self.db_path, ben, 1)
        undone = model.undo_repost(self.db_path, ben, 1)
        self.assertIsNotNone(undone["deleted_at"])
        with self.assertRaises(model.RuleBroken):
            model.undo_repost(self.db_path, ben, 1)   # nothing left to undo
        model.repost(self.db_path, ben, 1)

    def test_liking_or_answering_a_repost_acts_on_the_original(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.save_post(self.db_path, aiko, "hello")
        model.repost(self.db_path, ben, 1)
        model.like_post(self.db_path, chen, 2)
        self.assertEqual(view.like_counts_to_json(model.like_counts(self.db_path))[0]["post_id"], 1)
        self.assertEqual(model.save_post(self.db_path, chen, "hi!", 2)["reply_to"], 1)

    def test_a_repost_has_no_words_to_edit(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.repost(self.db_path, ben, 1)
        with self.assertRaises(model.RuleBroken):
            model.edit_post(self.db_path, ben, 2, "words")

    def test_a_repost_does_not_count_as_a_post_on_a_profile(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.repost(self.db_path, ben, 1)
        self.assertEqual(model.profile(self.db_path, "Ben")["posts"], 0)

    def test_a_deleted_post_cannot_be_reposted(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.delete_post(self.db_path, aiko, 1)
        with self.assertRaises(model.NotFound):
            model.repost(self.db_path, ben, 1)

    def test_quote_a_post(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        row = view.post_to_json(model.save_post(self.db_path, ben, "So true!", quote_of=1))
        self.assertEqual((row["text"], row["quote_of"]), ("So true!", 1))

    def test_a_quote_needs_words_and_a_post_to_quote(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, ben, "  ", quote_of=1)
        with self.assertRaises(model.NotFound):
            model.save_post(self.db_path, ben, "So true!", quote_of=7)
        with self.assertRaises(model.RuleBroken):
            model.save_post(self.db_path, ben, "So true!", reply_to=1, quote_of=1)

    # ---- Hashtags, mentions and search ----

    def test_tags_are_found_in_any_language_and_kept_in_small_letters(self):
        self.assertEqual(model.tags_in("Off to #Kyoto! #kyoto #漢字 #JLPT_N3 and # not"),
                         ["jlpt_n3", "kyoto", "漢字"])
        self.assertEqual(model.mentions_in("thanks @Ben and @ben, and @結衣!"), ["Ben", "結衣"])
        self.assertEqual(model.mentions_in("write to aiko@example.com"), [])
        self.assertEqual(model.tags_in("page#2"), [])

    def test_names_have_only_letters_numbers_and_underscores(self):
        for good in ["Aiko", "ben_2", "結衣"]:
            model.sign_up(self.db_path, good, PASSWORD)
        for wrong in ["Aiko Tanaka", "ben!", "@chen", "a/b"]:
            with self.assertRaises(model.RuleBroken):
                model.sign_up(self.db_path, wrong, PASSWORD)

    def test_search_by_tag(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "Fushimi Inari at 8am #Kyoto")
        model.save_post(self.db_path, aiko, "Ramen in #Osaka")
        model.save_post(self.db_path, aiko, "Back to #kyoto next week")
        self.assertEqual(model.search(self.db_path, "#KYOTO"), ([3, 1], []))

    def test_editing_or_deleting_a_post_changes_its_tags(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "Trip to #Nara")
        model.edit_post(self.db_path, aiko, 1, "Trip to #Kyoto")
        self.assertEqual(model.search(self.db_path, "#nara")[0], [])
        self.assertEqual(model.search(self.db_path, "#kyoto")[0], [1])
        model.delete_post(self.db_path, aiko, 1)
        self.assertEqual(model.search(self.db_path, "#kyoto")[0], [])

    def test_search_by_words_finds_posts_and_people(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.edit_profile(self.db_path, ben, "I love ramen")
        model.save_post(self.db_path, aiko, "Ramen in Osaka")
        model.save_post(self.db_path, aiko, "Curry at lunch")
        post_ids, people = model.search(self.db_path, "ramen")
        self.assertEqual(post_ids, [1])
        self.assertEqual([person["name"] for person in people], ["Ben"])

    def test_percent_and_underscore_are_ordinary_letters_in_a_search(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "100% done")
        model.save_post(self.db_path, aiko, "1000 done")
        self.assertEqual(model.search(self.db_path, "0%")[0], [1])

    def test_an_empty_search_is_refused(self):
        for wrong in ["", "   ", None, "a" * 101]:
            with self.assertRaises(model.RuleBroken):
                model.search(self.db_path, wrong)

    def test_older_posts_get_their_tags_when_the_server_starts(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "Old post about #Nara")
        connection = model.connect(self.db_path)
        connection.execute("DROP TABLE post_tags")   # as before tags were kept
        connection.commit()
        connection.close()
        model.create_tables(self.db_path)
        self.assertEqual(model.search(self.db_path, "#nara")[0], [1])

    # ---- Bookmarks ----

    def test_save_and_unsave_posts(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "first")
        model.save_post(self.db_path, aiko, "second")
        model.bookmark(self.db_path, ben, 1)
        self.assertEqual(model.bookmark(self.db_path, ben, 2), [2, 1])   # the latest saved first
        with self.assertRaises(model.RuleBroken):
            model.bookmark(self.db_path, ben, 1)
        self.assertEqual(model.remove_bookmark(self.db_path, ben, 1), [2])
        with self.assertRaises(model.RuleBroken):
            model.remove_bookmark(self.db_path, ben, 1)

    def test_bookmarks_are_each_persons_own(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.bookmark(self.db_path, ben, 1)
        self.assertEqual(model.bookmarks_of(self.db_path, aiko), [])

    def test_a_deleted_post_leaves_the_bookmarks(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.bookmark(self.db_path, ben, 1)
        model.delete_post(self.db_path, aiko, 1)
        self.assertEqual(model.bookmarks_of(self.db_path, ben), [])

    # ---- Notifications ----

    def told(self, user_id):
        """What this user was told, as (kind, who did it, post id), oldest first."""
        rows = view.notifications_to_json(model.notifications_of(self.db_path, user_id))
        return [(row["kind"], row["actor"], row["post_id"]) for row in reversed(rows)]

    def test_likes_reposts_quotes_replies_mentions_and_follows_are_told(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.save_post(self.db_path, aiko, "hello")                      # 1
        model.like_post(self.db_path, ben, 1)
        model.repost(self.db_path, ben, 1)                                # 2
        model.save_post(self.db_path, chen, "So true", quote_of=1)        # 3
        model.save_post(self.db_path, ben, "hi!", reply_to=1)             # 4
        model.save_post(self.db_path, chen, "Thanks @aiko and @Nobody")   # 5
        model.follow(self.db_path, ben, "Aiko")
        self.assertEqual(self.told(aiko), [("like", "Ben", 1), ("repost", "Ben", 1), ("quote", "Chen", 3),
                                           ("reply", "Ben", 4), ("mention", "Chen", 5), ("follow", "Ben", None)])

    def test_nobody_is_told_about_their_own_actions(self):
        aiko = self.user("Aiko")
        model.save_post(self.db_path, aiko, "hello")
        model.like_post(self.db_path, aiko, 1)
        model.save_post(self.db_path, aiko, "me again, @Aiko", reply_to=1)
        self.assertEqual(self.told(aiko), [])

    def test_undoing_takes_the_notification_back(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.like_post(self.db_path, ben, 1)
        model.repost(self.db_path, ben, 1)
        model.follow(self.db_path, ben, "Aiko")
        model.unlike_post(self.db_path, ben, 1)
        model.undo_repost(self.db_path, ben, 1)
        model.unfollow(self.db_path, ben, "Aiko")
        self.assertEqual(self.told(aiko), [])

    def test_the_same_thing_is_told_once(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.save_post(self.db_path, ben, "hey @Aiko @aiko")             # 2
        model.edit_post(self.db_path, ben, 2, "hey @Aiko!")
        self.assertEqual(self.told(aiko), [("mention", "Ben", 2)])

    def test_a_deleted_post_takes_its_notifications_with_it(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "hello")
        model.save_post(self.db_path, ben, "hi @Aiko", reply_to=1)
        model.delete_post(self.db_path, ben, 2)
        self.assertEqual(self.told(aiko), [])

    def test_unread_then_read(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.follow(self.db_path, ben, "Aiko")
        self.assertEqual(model.unread_notifications(self.db_path, aiko), 1)
        self.assertEqual(model.unread_notifications(self.db_path, ben), 0)   # each person's own
        model.read_notifications(self.db_path, aiko)
        self.assertEqual(model.unread_notifications(self.db_path, aiko), 0)

    # ---- The sidebar ----

    def test_trends_are_the_most_used_tags_of_the_last_week(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.save_post(self.db_path, aiko, "#kyoto #ramen")
        model.save_post(self.db_path, ben, "#Kyoto again")
        model.save_post(self.db_path, ben, "#nara", posted_at="2000-01-01 10:00")   # too long ago
        model.save_post(self.db_path, aiko, "#gone")
        model.delete_post(self.db_path, aiko, 4)
        rows = [(row["tag"], row["posts"]) for row in model.trends(self.db_path)]
        self.assertEqual(rows, [("kyoto", 2), ("ramen", 1)])

    def test_suggestions_leave_out_you_and_who_you_follow(self):
        aiko, ben, chen, dana = self.user("Aiko"), self.user("Ben"), self.user("Chen"), self.user("Dana")
        model.follow(self.db_path, ben, "Chen")
        model.follow(self.db_path, dana, "Chen")
        model.follow(self.db_path, aiko, "Ben")
        names = [row["name"] for row in model.suggestions(self.db_path, aiko)]
        self.assertEqual(names, ["Chen", "Dana"])          # not Aiko, not Ben; Chen has most followers
        everyone = [row["name"] for row in model.suggestions(self.db_path, None)]
        self.assertEqual(everyone, ["Chen", "Ben", "Aiko"])   # for a visitor: the most followed

    # ---- Direct messages ----

    def test_send_and_read_messages(self):
        aiko, ben = self.user("Aiko"), self.user("Ben")
        model.send_message(self.db_path, aiko, "ben", " Are you going to Kyoto on Saturday? ")
        model.send_message(self.db_path, ben, "Aiko", "Yes! 7:10 train.")
        person, rows = model.conversation(self.db_path, aiko, "Ben")
        self.assertEqual(person["name"], "Ben")
        self.assertEqual([(view.message_to_json(row)["from_me"], row["text"]) for row in rows],
                         [(True, "Are you going to Kyoto on Saturday?"), (False, "Yes! 7:10 train.")])

    def test_only_the_two_people_can_read_a_conversation(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.send_message(self.db_path, aiko, "Ben", "a secret")
        self.assertEqual(model.conversation(self.db_path, chen, "Ben")[1], [])
        self.assertEqual(model.conversation(self.db_path, chen, "Aiko")[1], [])
        self.assertEqual(model.conversations(self.db_path, chen), [])

    def test_the_conversation_list_has_the_newest_message_and_the_unread_count(self):
        aiko, ben, chen = self.user("Aiko"), self.user("Ben"), self.user("Chen")
        model.send_message(self.db_path, ben, "Aiko", "hi")
        model.send_message(self.db_path, ben, "Aiko", "are you there?")
        model.send_message(self.db_path, chen, "Aiko", "hello!")
        model.send_message(self.db_path, aiko, "Chen", "hey Chen")
        rows = view.conversations_to_json(model.conversations(self.db_path, aiko))
        self.assertEqual([(r["name"], r["text"], r["from_me"], r["unread"]) for r in rows],
                         [("Chen", "hey Chen", True, 1), ("Ben", "are you there?", False, 2)])
        self.assertEqual(model.unread_messages(self.db_path, aiko), 3)
        model.read_conversation(self.db_path, aiko, "Ben")
        self.assertEqual(model.unread_messages(self.db_path, aiko), 1)

    def test_message_rules(self):
        aiko = self.user("Aiko")
        self.user("Ben")
        for to, text in [("Aiko", "talking to myself"), ("Nobody", "hello"), ("Ben", "   "),
                         ("Ben", "a" * 1001)]:
            with self.assertRaises(model.RuleBroken):
                model.send_message(self.db_path, aiko, to, text)
        model.send_message(self.db_path, aiko, "Ben", "a" * 1000)

    def test_the_database_itself_refuses_a_message_to_yourself(self):
        self.user("Aiko")
        connection = model.connect(self.db_path)
        with self.assertRaises(sqlite3.IntegrityError):
            connection.execute("INSERT INTO messages (sender_id, receiver_id, text, sent_at) "
                               "VALUES (1, 1, 'hi', 'now')")
        connection.close()

class BellTests(unittest.TestCase):

    def test_a_ring_wakes_a_waiting_request(self):
        bell = server.Bell()
        threading.Timer(0.05, bell.ring).start()
        self.assertEqual(bell.wait(0, timeout=5), 1)

    def test_without_a_ring_the_wait_ends_after_the_timeout(self):
        bell = server.Bell()
        self.assertEqual(bell.wait(0, timeout=0.05), 0)


class SeedTests(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.folder.name, "test.db")
        self.rounds = model.PASSWORD_ROUNDS
        model.PASSWORD_ROUNDS = 1000

    def tearDown(self):
        model.PASSWORD_ROUNDS = self.rounds
        self.folder.cleanup()

    def test_seed_makes_a_lively_timeline(self):
        made = seed.seed(self.db_path)
        self.assertEqual(made["people"], len(seed.PEOPLE))
        self.assertGreater(made["likes"], 0)
        self.assertGreater(made["follows"], 0)
        rows = view.posts_to_json(model.posts_after(self.db_path, 0))
        self.assertEqual(len(rows), len(seed.POSTS))
        self.assertTrue(any(row["reply_to"] for row in rows))
        self.assertEqual(len([row for row in rows if row["deleted_at"]]), len(seed.DELETES))
        self.assertEqual(len([row for row in rows if row["edited_at"]]), len(seed.EDITS))
        times = [row["posted_at"] for row in rows]
        self.assertEqual(times, sorted(times))   # oldest first, as the ids are

    def test_the_made_up_data_has_every_kind_of_thing(self):
        seed.seed(self.db_path)
        aiko = model.log_in(self.db_path, "Aiko", seed.PASSWORD)
        aiko_id = model.user_for_token(self.db_path, aiko)["id"]
        rows = view.posts_to_json(model.posts_after(self.db_path, 0))
        self.assertTrue(any(row["repost_of"] for row in rows))
        self.assertTrue(any(row["quote_of"] for row in rows))
        self.assertTrue(model.trends(self.db_path))
        self.assertTrue(model.profile(self.db_path, "Aiko")["bio"])
        self.assertTrue(model.bookmarks_of(self.db_path, aiko_id))
        self.assertTrue(model.conversations(self.db_path, aiko_id))
        self.assertTrue(model.notifications_of(self.db_path, aiko_id))
        self.assertGreater(model.unread_messages(self.db_path, aiko_id), 0)   # something new to see

    def test_welcome_fills_a_real_accounts_notifications_messages_and_bookmarks(self):
        seed.seed(self.db_path)
        token = model.sign_up(self.db_path, "Alex", PASSWORD)
        alex = model.user_for_token(self.db_path, token)["id"]
        done = seed.welcome(self.db_path, "alex")
        self.assertEqual(done["messages"], 3)
        kinds = {row["kind"] for row in model.notifications_of(self.db_path, alex)}
        self.assertEqual(kinds, {"follow", "like", "reply", "mention", "repost", "quote"})
        self.assertGreater(model.unread_notifications(self.db_path, alex), 0)
        self.assertEqual(model.unread_messages(self.db_path, alex), 3)
        self.assertEqual(len(model.bookmarks_of(self.db_path, alex)), 3)
        rows = view.posts_to_json(model.posts_after(self.db_path, 0))
        self.assertIn(("Alex", seed.WELCOME_POST), [(row["author"], row["text"]) for row in rows])
        joined = model.profile(self.db_path, "Alex")["joined_at"]
        told = model.notifications_of(self.db_path, alex)
        self.assertTrue(all(row["created_at"] >= joined for row in told))   # nothing before Alex joined
        again = seed.welcome(self.db_path, "Alex")            # twice does no harm
        self.assertEqual(again["follows"] + again["likes"] + again["reposts"] + again["bookmarks"], 0)
        self.assertIs(model.now.__name__, "now")               # the real clock is back

    def test_welcome_needs_a_real_account_and_the_made_up_people(self):
        with self.assertRaises(SystemExit):
            seed.welcome(self.db_path, "Alex")                # nobody is here yet
        seed.seed(self.db_path)
        for wrong in ["Nobody", "Aiko"]:
            with self.assertRaises(SystemExit):
                seed.welcome(self.db_path, wrong)

    def test_the_seed_puts_the_real_clock_back(self):
        real_now = model.now
        seed.seed(self.db_path)
        self.assertIs(model.now, real_now)

    def test_a_made_up_person_can_log_in(self):
        seed.seed(self.db_path)
        token = model.log_in(self.db_path, "Aiko", seed.PASSWORD)
        self.assertEqual(model.user_for_token(self.db_path, token)["name"], "Aiko")

    def test_seed_refuses_a_timeline_that_is_not_empty(self):
        seed.seed(self.db_path)
        with self.assertRaises(SystemExit):
            seed.seed(self.db_path)


class RealServerTest(unittest.TestCase):

    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        db_path = os.path.join(self.folder.name, "test.db")
        self.rounds = model.PASSWORD_ROUNDS
        model.PASSWORD_ROUNDS = 1000
        # Port 0 asks the computer for any free port.
        self.server = server.make_server(0, db_path)
        self.base = "http://127.0.0.1:" + str(self.server.server_address[1])
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        model.PASSWORD_ROUNDS = self.rounds
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
        self.assertEqual(self.send(aiko, "GET", "/me"), (200, {"name": "Aiko", "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": []}))
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
        self.assertEqual(self.send(stranger, "GET", "/me"), (200, {"name": None, "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": []}))
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
        self.assertEqual(self.send(aiko, "GET", "/me"), (200, {"name": None, "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": []}))
        self.assertEqual(self.send(aiko, "POST", "/posts", {"text": "hello"})[0], 401)
        status, _ = self.send(aiko, "POST", "/login", {"name": "Aiko", "password": "wrong one"})
        self.assertEqual(status, 400)
        status, me = self.send(aiko, "POST", "/login", {"name": "Aiko", "password": PASSWORD})
        self.assertEqual((status, me), (200, {"name": "Aiko", "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": []}))

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


    def test_a_profile_over_http(self):
        aiko = self.signed_up("Aiko")
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        status, answer = self.send(self.browser(), "GET", "/users?name=aiko")
        self.assertEqual((status, answer["name"], answer["posts"]), (200, "Aiko", 1))
        self.assertEqual(self.send(aiko, "GET", "/users?name=Nobody")[0], 404)


    def test_follow_over_http(self):
        aiko = self.signed_up("Aiko")
        self.signed_up("Ben")
        self.assertEqual(self.send(self.browser(), "POST", "/follows", {"name": "Ben"})[0], 401)
        self.assertEqual(self.send(aiko, "POST", "/follows", {"name": "ben"}),
                         (201, {"name": "Aiko", "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": ["Ben"]}))
        self.assertTrue(self.send(aiko, "GET", "/users?name=Ben")[1]["you_follow"])
        self.assertEqual(self.send(aiko, "GET", "/me")[1]["following"], ["Ben"])
        self.assertEqual(self.send(aiko, "DELETE", "/follows", {"name": "Ben"}),
                         (200, {"name": "Aiko", "unread_notifications": 0, "unread_messages": 0, "bio": "", "avatar": None, "following": []}))


    def open_events(self):
        """Open /events, as the page's EventSource does, and read up to its first message."""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1],
                                                timeout=5)
        connection.request("GET", "/events")
        events = connection.getresponse()
        self.assertEqual(events.getheader("Content-Type"), "text/event-stream")
        self.assertEqual(self.next_message(events), "hello")
        return connection, events

    def next_message(self, events):
        """Read lines until a "data:" line, and return what it says."""
        while True:
            line = events.readline().decode("utf-8")
            if line.startswith("data: "):
                return line[len("data: "):].strip()

    def test_live_updates_tell_every_window_about_a_change(self):
        aiko = self.signed_up("Aiko")
        first, first_events = self.open_events()
        second, second_events = self.open_events()
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        self.assertEqual(self.next_message(first_events), "changed")
        self.assertEqual(self.next_message(second_events), "changed")
        first.close()
        second.close()

    def test_a_refused_request_does_not_ring_the_bell(self):
        aiko = self.signed_up("Aiko")
        rings = self.server.bell.rings
        self.send(aiko, "POST", "/posts", {"text": ""})
        self.send(self.browser(), "POST", "/posts", {"text": "not logged in"})
        self.send(aiko, "GET", "/posts?after=0")
        self.assertEqual(self.server.bell.rings, rings)


    def get_raw(self, path):
        """Ask for an address exactly as written, without the browser tidying it first."""
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_address[1], timeout=5)
        connection.request("GET", path)
        answer = connection.getresponse()
        result = answer.status, answer.getheader("Content-Type"), answer.read()
        connection.close()
        return result

    def test_the_page_files_are_served(self):
        status, content_type, body = self.get_raw("/")
        self.assertEqual((status, content_type), (200, "text/html; charset=utf-8"))
        self.assertIn(b"<html", body)
        status, content_type, _ = self.get_raw("/js/main.js")
        self.assertEqual((status, content_type), (200, "text/javascript; charset=utf-8"))

    def test_nothing_outside_the_page_folder_is_served(self):
        for path in ["/model.py", "/server.py", "/timeline.db", "/../model.py", "/js/../../model.py",
                     "/%2e%2e/model.py", "/page/index.html", "/nothing.js"]:
            self.assertEqual(self.get_raw(path)[0], 404, path)


    def test_edit_profile_over_http(self):
        aiko = self.signed_up("Aiko")
        self.assertEqual(self.send(self.browser(), "PUT", "/me", {"bio": "hi"})[0], 401)
        status, me = self.send(aiko, "PUT", "/me", {"bio": "Kyoto weekends."})
        self.assertEqual((status, me["bio"]), (200, "Kyoto weekends."))
        self.assertEqual(self.send(aiko, "GET", "/users?name=Aiko")[1]["bio"], "Kyoto weekends.")
        self.assertEqual(self.send(aiko, "PUT", "/me", {"bio": "a" * 161})[0], 400)


    def upload(self, browser, data, content_type="image/png"):
        request = urllib.request.Request(self.base + "/uploads", method="POST", data=data,
                                         headers={"Content-Type": content_type})
        try:
            with browser.open(request) as answer:
                return answer.status, json.loads(answer.read())
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.loads(error.read())

    def test_pictures_over_http(self):
        aiko = self.signed_up("Aiko")
        png = b"\x89PNG\r\n\x1a\n" + b"made-up picture bytes"
        self.assertEqual(self.upload(self.browser(), png)[0], 401)
        self.assertEqual(self.upload(aiko, b"<svg><script/></svg>", "image/svg+xml")[0], 400)
        status, picture = self.upload(aiko, png)
        self.assertEqual(status, 201)
        status, post = self.send(aiko, "POST", "/posts", {"text": "", "picture_id": picture["id"]})
        self.assertEqual((status, post["picture"]), (201, picture["url"]))
        status, content_type, body = self.get_raw(picture["url"])
        self.assertEqual((status, content_type, body), (200, "image/png", png))
        with urllib.request.urlopen(self.base + picture["url"]) as answer:
            self.assertEqual(answer.headers["X-Content-Type-Options"], "nosniff")
        for wrong in ["/uploads/../model.py", "/uploads/%2e%2e/timeline.db", "/uploads/nothing.png"]:
            self.assertEqual(self.get_raw(wrong)[0], 404, wrong)

    def test_a_profile_picture_over_http(self):
        aiko = self.signed_up("Aiko")
        _, picture = self.upload(aiko, b"GIF89a made-up")
        status, me = self.send(aiko, "PUT", "/me", {"avatar_id": picture["id"]})
        self.assertEqual((status, me["avatar"]), (200, picture["url"]))
        self.assertEqual(self.send(aiko, "GET", "/people")[1], [{"name": "Aiko", "avatar": picture["url"]}])


    def test_reposts_and_quotes_over_http(self):
        aiko, ben = self.signed_up("Aiko"), self.signed_up("Ben")
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        self.assertEqual(self.send(self.browser(), "POST", "/reposts", {"post_id": 1})[0], 401)
        status, repost = self.send(ben, "POST", "/reposts", {"post_id": 1})
        self.assertEqual((status, repost["repost_of"]), (201, 1))
        self.assertEqual(self.send(ben, "POST", "/reposts", {"post_id": 1})[0], 400)
        status, undone = self.send(ben, "DELETE", "/reposts", {"post_id": 1})
        self.assertEqual(status, 200)
        self.assertIsNotNone(undone["deleted_at"])
        status, quote = self.send(ben, "POST", "/posts", {"text": "So true!", "quote_of": 1})
        self.assertEqual((status, quote["quote_of"]), (201, 1))


    def test_search_over_http(self):
        aiko = self.signed_up("Aiko")
        self.send(aiko, "POST", "/posts", {"text": "Hello #Hirakata"})
        status, found = self.send(self.browser(), "GET", "/search?q=%23hirakata")
        self.assertEqual((status, found["post_ids"]), (200, [1]))
        status, found = self.send(self.browser(), "GET", "/search?q=aik")
        self.assertEqual(found["people"], [{"name": "Aiko", "bio": "", "avatar": None}])
        self.assertEqual(self.send(self.browser(), "GET", "/search?q=")[0], 400)


    def test_bookmarks_over_http(self):
        aiko, ben = self.signed_up("Aiko"), self.signed_up("Ben")
        self.send(aiko, "POST", "/posts", {"text": "hello"})
        self.assertEqual(self.send(self.browser(), "GET", "/bookmarks")[0], 401)
        self.assertEqual(self.send(ben, "POST", "/bookmarks", {"post_id": 1}), (201, {"post_ids": [1]}))
        self.assertEqual(self.send(aiko, "GET", "/bookmarks"), (200, {"post_ids": []}))
        self.assertEqual(self.send(ben, "DELETE", "/bookmarks", {"post_id": 1}), (200, {"post_ids": []}))


    def test_notifications_over_http(self):
        aiko, ben = self.signed_up("Aiko"), self.signed_up("Ben")
        self.send(ben, "POST", "/follows", {"name": "Aiko"})
        self.assertEqual(self.send(self.browser(), "GET", "/notifications")[0], 401)
        self.assertEqual(self.send(aiko, "GET", "/me")[1]["unread_notifications"], 1)
        status, told = self.send(aiko, "GET", "/notifications")
        self.assertEqual((status, [(n["kind"], n["actor"], n["read"]) for n in told]),
                         (200, [("follow", "Ben", False)]))
        self.assertEqual(self.send(ben, "GET", "/notifications"), (200, []))   # not Aiko's
        status, me = self.send(aiko, "POST", "/notifications/read")
        self.assertEqual((status, me["unread_notifications"]), (200, 0))


    def test_sidebar_over_http(self):
        aiko = self.signed_up("Aiko")
        self.signed_up("Ben")
        self.send(aiko, "POST", "/posts", {"text": "Hello #Hirakata"})
        status, side = self.send(aiko, "GET", "/sidebar")
        self.assertEqual((status, side["trends"]), (200, [{"tag": "hirakata", "posts": 1}]))
        self.assertEqual([person["name"] for person in side["suggestions"]], ["Ben"])


    def test_messages_over_http(self):
        aiko, ben, chen = self.signed_up("Aiko"), self.signed_up("Ben"), self.signed_up("Chen")
        self.assertEqual(self.send(self.browser(), "GET", "/messages")[0], 401)
        status, sent = self.send(aiko, "POST", "/messages", {"to": "Ben", "text": "hi Ben"})
        self.assertEqual((status, sent["from_me"], sent["text"]), (201, True, "hi Ben"))
        self.assertEqual(self.send(ben, "GET", "/me")[1]["unread_messages"], 1)
        status, chat = self.send(ben, "GET", "/messages?with=aiko")
        self.assertEqual((status, chat["with"], [m["text"] for m in chat["messages"]]), (200, "Aiko", ["hi Ben"]))
        self.assertEqual(self.send(chen, "GET", "/messages?with=Aiko")[1]["messages"], [])   # not Chen's
        status, me = self.send(ben, "POST", "/messages/read", {"with": "Aiko"})
        self.assertEqual((status, me["unread_messages"]), (200, 0))
        self.assertEqual([c["name"] for c in self.send(ben, "GET", "/messages")[1]], ["Aiko"])


if __name__ == "__main__":
    unittest.main()
