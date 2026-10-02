# Design doc — Timeline

*Every name and example row here is made up.*

---

*The product spec*

## 1. The problem

When two people use the same app, each needs to see what the other posted. A page that keeps
everything in the browser cannot do that: each person's device keeps its own copy. Timeline is a
small Twitter-like app built to show the difference. One version keeps everything in the page, and
the other has a backend that every window shares.

## 2. Not in this version

- No accounts, passwords or sign-in. Each window types a display name.
- No follows. They are left for whoever extends the app.
- No pictures. A picture needs a second kind of storage for its files, which is a design of its own.
- No realtime connection (no WebSockets). The page asks for new posts once a second.
- Nothing reachable from another machine. The server listens on `127.0.0.1` only.
- No libraries, no install, no build step.

## 3. Screens

One screen, the same in both versions:

- **The timeline.** A name field at the top, a *What is happening?* box with a live count
  (*x / 280*) and a **Post** button, and the timeline below it, newest first (author, text, time, and the buttons **♡ Like** with its count, **Reply**, and
  **Edit** and **Delete** on your own posts). Replies sit under their post, oldest first. Reply and Edit use the same
  box as a new post, with a line above it (*Replying to Aiko* or *Editing your post*) and **Cancel**.
  A deleted post shows only *This post was deleted.*, with its replies still under it.
  Its one job: show everyone's posts, and take a new one, a reply, an edit, a delete or a like.

Large type and high contrast, so that it can be read from across a room.

---

*The engineering design*

## 4. The three parts

```
the browser                          the server                   the store
index.html · style.css · app.js  ──  server.py  ──────────────────  timeline.db
         a new post, "anything new?" ▶          save this, give me the newest ▶
         ◀ saved, the newest posts               ◀ the rows
```

| Part | `page-only/` | `with-backend/` |
|---|---|---|
| **Frontend** (runs on the user's device) | `index.html` · `style.css` · `app.js` | the same three files; `app.js` talks to the server instead of the browser |
| **Backend** (runs on the server) | none: the rules run in `app.js` | `server.py`, Python 3 standard library (`http.server`), written in three labelled parts: **controller · model · view** |
| **Data** (runs on the server) | the browser's `sessionStorage` | `timeline.db`, one SQLite file with three tables, `users`, `posts` and `likes`, created by the server when it starts |

**Technologies, and why each one.**

- **Plain HTML, CSS and JavaScript.** Three files, each with one job: structure, looks, behaviour.
- **Python 3 standard library only** (`http.server`, `sqlite3`, `json`). Python ships on a Mac, so
  there is nothing to install. The code avoids anything newer than Python 3.9.
- **SQLite.** One file, no database server of its own, and the `sqlite3` command can open it.
- **Polling, once a second.** `fetch('/posts?after=<last id>')` on a timer: each window asks the
  server *anything new?* It is the simplest thing that works.
- **`sessionStorage`, not `localStorage`, for the page-only version.** Two normal windows of one
  browser share `localStorage`, which would make the page-only version look shared. `sessionStorage`
  belongs to one window, as each person's phone has its own storage, and it survives a reload.

**The interfaces.**

| Request | What goes in | What comes out |
|---|---|---|
| `POST /posts` | `{"author": "Aiko", "text": "the library is open late tonight"}`, and `"reply_to": 3` for a reply | the saved post, with its `id` and `posted_at` · or `400` with the rule it broke |
| `PUT /posts` | `{"post_id": 3, "name": "Aiko", "text": "…"}` | the edited post, with its `edited_at` · or `400` with the rule it broke |
| `DELETE /posts` | `{"post_id": 3, "name": "Aiko"}` | the deleted post: empty `text`, with its `deleted_at` · or `400` with the rule it broke |
| `GET /posts?after=12` | the last `id` this window has | every post with a larger `id`, oldest first |
| `POST /likes` | `{"post_id": 3, "name": "Ben"}` | every post's likes, as `GET /likes` · or `400` with the rule it broke |
| `DELETE /likes` | `{"post_id": 3, "name": "Ben"}` | every post's likes, as `GET /likes` · or `400` with the rule it broke |
| `GET /likes?name=Ben` | the name in this window's box | `[{"post_id": 3, "likes": 2, "you_liked": true}, …]`, every post with at least one like |
| `GET /changes` | nothing | every edited or deleted post, oldest first |
| `GET /` and the three files | nothing | the page |

**The model's rules:** text is not empty after trimming · text is at most 280 characters · author
is not empty, at most 40 characters · a like, a reply and an edit name a post that exists · a name likes a post at most once, and
takes back only a like it made · only the author can edit or delete a post, and the edit follows the text rules · a deleted post
cannot be liked, edited, replied to or deleted again. The server checks them even though the page checks for an
empty post too, because a user can change anything that runs on their own device.

## 5. The data model

Three tables:

| `users` | |
|---|---|
| `id` | integer, primary key, given by SQLite |
| `name` | text, the display name, unique |

| `posts` | |
|---|---|
| `id` | integer, primary key, given by SQLite |
| `author_id` | integer, foreign key: the `id` of a row in `users` |
| `text` | text |
| `posted_at` | text, `HH:MM`, local time |
| `reply_to` | integer, foreign key: the `id` of the post this one answers · empty for a post |
| `edited_at` | text, `HH:MM`, local time of the last edit · empty if never edited |
| `deleted_at` | text, `HH:MM`, local time it was deleted · empty if not deleted |

| `likes` | |
|---|---|
| `post_id` | integer, foreign key: the `id` of a row in `posts` |
| `user_id` | integer, foreign key: the `id` of a row in `users` |
| primary key | the pair `(post_id, user_id)`, so the database keeps each pair once |

Example rows: `users` `1 · Aiko` · `2 · Ben` · `posts` `1 · 1 · the library is open late tonight ·
15:42` · `2 · 2 · thanks! · 15:42`.

There are no accounts, so a user is found by name: the first post with a new name adds that person
to `users`, and every later post with the same name points at the same row. Each name is kept once,
and each post points at its author by number.

A like is a pair of numbers: which post, and which user. The table keeps no names and no counts; the
count is worked out with `COUNT(*)` when a window asks. The primary key is what stops a second like:
the database refuses the same pair twice, even when two requests arrive at the same moment. Without
accounts, it stops a *name* from liking twice, not a person who types a different name. An unlike
deletes the row, so the count goes down by itself.

A reply is a post with `reply_to` set, so it can be liked, edited and replied to like any post. An
edit changes `text` and sets `edited_at`; the old text is not kept. "Your own post" means a post whose
author has the name in your box, so, as with likes, anyone who types that name can edit it.

A delete erases the post's `text` and its likes, but keeps its row: other people's replies point at
it by `reply_to`, and deleting your post should not delete what they wrote. So the page shows *This
post was deleted.* in its place, with the replies under it.

A `timeline.db` from before replies, edits and deleting is kept: when the server starts, it adds the
missing columns, empty.

## 6. How I will know it works

1. When a post is sent with text, it should come back with an `id` and a time, and the same name
   should always point at the same user.
2. When a window asks for posts after an `id`, it should get only newer posts, oldest first.
3. When two windows are open on the backend version, a post from one should appear in the other
   within a second.
4. **And when it goes wrong:** when a post is empty, or longer than 280 characters, the server
   should refuse it and say which rule it broke. When the server is stopped, the page should say
   *Cannot reach the server*, and recover by itself when the server starts again.

Sentences 1 and 2, and the first half of 4, are checked by `make test`. Sentence 3 and the second
half of 4 are browser behaviour, and are checked by hand, in two windows.

---

## 7. Adversarial review

| Objection | About | Decision | Why | What changed |
|---|---|---|---|---|
| Two normal windows share `localStorage`, so the page-only version looks shared. | design | accept | It hides the one thing the app exists to show. | The page-only version uses `sessionStorage`. |
| The error message says "280" even if the limit is changed. | design | accept | A rule should be written in one place. | The message reads the limit from the rule. |
| The author's name is copied into every post, so a rename would break old posts. | design | accept | One fact, one place, even without accounts. | A `users` table; each post points at its author by `author_id`. |
| Pictures would make posts more realistic. | product | reject | A picture needs file storage as well as the database. | Nothing; section 2 says so. |
| The page should check every rule, not only an empty post. | design | reject | The server is where the rules count, and a long post shows the server refusing it. | Nothing. |

## 8. Build or borrow

- **Built:** the page, the server and the data model.
- **Borrowed:** Python and its standard library, SQLite (which comes with Python), and the browser.

---

## Files

```
README.md            what it is, how to run it, things to try
AGENTS.md            what each file does, for an AI agent working here
DESIGN.md            this document
Makefile             make run · make test · make reset
.claude/launch.json  starts the backend version from the Claude Code desktop app
page-only/           open index.html; nothing to start
  index.html  style.css  app.js
with-backend/        make run, then http://localhost:8010
  index.html  style.css  app.js
  server.py          controller · model · view, labelled
  test_server.py     unittest: the rules, saving, "after", likes, replies, edits, deletes, real round trips
```

`timeline.db` is created next to `server.py` and is git-ignored. `make reset` deletes it.
