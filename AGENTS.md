# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language. Explain in short, plain sentences, and define a technical word the first time you
use it. When you change code, say which file changed and why.

## What this is

Timeline, the advanced version: people sign up, post short messages, reply, like, edit and delete
their own posts, follow each other, and open each other's profiles. Every open window sees every
change at once. The look follows the Kansai Gaidai Asian Studies Program site.

This folder is a copy of the simple Timeline, which lives in its own folder and is kept as it was.
There is no `page-only/` version here: without a server there can be no accounts or live updates.

## What each file does

| File | Its one job |
|---|---|
| `with-backend/index.html` | The parts of the screen: top bar, log-in box, post box, tabs, profile, timeline. |
| `with-backend/style.css` | How the screen looks: the colours and fonts of the theme, in light and dark. |
| `with-backend/app.js` | Sends each action to the server, listens to `/events`, and shows the screen the address asks for. |
| `with-backend/server.py` | The backend, in three labelled parts: **controller**, **model**, **view**. |
| `with-backend/seed.py` | Fills an empty timeline with made-up people and posts, through the model. |
| `with-backend/test_server.py` | The checks for `server.py` and `seed.py`. |
| `with-backend/timeline.db` | The database. The server creates it when it starts. It is not in git. |
| `Makefile` | Short commands: `make run`, `make test`, `make reset`, `make seed`. |

The three parts of `server.py`:

- **Controller** (`TimelineHandler`): reads each request and picks what to do. Each request has a
  method named after it (`POST /likes` is `post_likes`), listed in `ROUTES`. It reads the session
  cookie and asks the model who that is. After every saved change it rings the bell, so that every
  open `/events` connection says `changed`.
- **Model**: the rules, and the database, in five tables: `users` (each person once, with a password
  hash), `sessions` (one per logged-in browser, with a token hash), `posts` (each points at its author
  by `author_id`, and a reply at its post by `reply_to`), `likes` and `follows` (pairs of ids, each
  pair once). A name is kept once, in `users`; never copy it into another table. Never store a
  password or a session token; store only their hashes.
- **View** (`me_to_json`, `profile_to_json`, `post_to_json`, `like_count_to_json` and the lists of
  them): turns database rows into the JSON the page reads.

## How to run it

- `make run`, then open <http://localhost:8010>. Press Ctrl+C to stop.
- A timeline with made-up people and posts: `make reset seed`. They all have the password `timeline123`.
- Start again with an empty timeline: `make reset`.
- See what is saved: `sqlite3 with-backend/timeline.db 'select id, name, joined_at from users; select * from posts'`

It needs only `python3` (3.9 or newer). Do not add libraries, packages or a build step.
Write code that runs on Python 3.9: no `match` statements, and no `X | Y` in type hints.

## How to test it

`make test`. Every test must pass before and after a change. A new feature gets a new test in
`with-backend/test_server.py`. The tests lower `PASSWORD_ROUNDS` so they stay fast; keep doing that
in any new test that signs people up.

## The one rule

**Keep the three parts of `server.py` separate. A new rule goes in the model.** The controller does
not check rules and does not touch the database. The view does not decide anything. If a feature
needs a new rule, write it in the model, and check it in the page too, because the page and the
server must agree. The server always checks, even when the page already did, because a user can change anything that
runs on their own device. Who is asking comes from the session cookie, never from the request body.
