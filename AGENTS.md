# AGENTS.md — for the AI agent working in this repository

The person asking you may be new to programming, and may read English as a second language. Explain in short, plain sentences, and define a technical word the first time you
use it. When you change code, say which file changed and why.

## What this is

Timeline, the advanced version: a small social app with the familiar three columns (menu, timeline,
sidebar). People sign up, post (with a picture if they like), reply, repost, quote, like, bookmark,
edit and delete their own posts, use #tags and @mentions, search, follow each other, get
notifications, and send private messages. Every open window sees every change at once. The look
follows the Kansai Gaidai Asian Studies Program site; the logo (結) is our own, not the university's.

This is a copy of the simple Timeline, which is kept as it was in its own repository,
[anyone-can-build-timeline](https://github.com/Compiledex/anyone-can-build-timeline).

## What each file does

| File | Its one job |
|---|---|
| `with-backend/server.py` | The **controller**: reads each request, asks the model, sends the answer. The file you start. |
| `with-backend/model.py` | The **model**: every rule, and the only code that reads or writes the database and the uploads folder. |
| `with-backend/view.py` | The **view**: turns database rows into the JSON the page reads. |
| `with-backend/seed.py` | Fills an empty timeline with made-up people, posts and messages, through the model. |
| `with-backend/test_server.py` | The checks for all of the above. |
| `with-backend/page/index.html` | The parts of the screen: the three columns, the post box, the windows (`<dialog>`). |
| `with-backend/page/style.css` | How it looks, in light and dark, after the Kansai Gaidai site. |
| `with-backend/page/js/main.js` | Starts the page: the address, live updates, drawing the screen, what the buttons do. |
| `with-backend/page/js/state.js` | Everything the window knows. Every screen is drawn from it. |
| `with-backend/page/js/api.js` | Talking to the server. |
| `with-backend/page/js/screens.js` | The screens: Home, a post, a profile, Explore, Notifications, Messages, Bookmarks, the sidebar. |
| `with-backend/page/js/render.js` | Drawing one thing: a post card, an avatar, a thread, links in a post. |
| `with-backend/page/js/dialogs.js` | The windows: log in, write (post, reply, quote, edit), edit profile. |
| `with-backend/page/js/pictures.js` | Choosing and uploading a picture. |
| `with-backend/page/js/format.js` | Times, initials, avatar colours, and the addresses of the screens. |
| `with-backend/page/js/icons.js` | The icons, as simple line drawings. |
| `with-backend/timeline.db`, `with-backend/uploads/` | The database and the uploaded pictures. Made by the server. Not in git. |
| `Makefile` | Short commands: `make run`, `make test`, `make reset`, `make seed`. |

The three parts of the backend:

- **Controller** (`server.py`, `TimelineHandler`): each request has a method named after it
  (`POST /likes` is `post_likes`), listed in `ROUTES`. It reads the session cookie, asks the model who
  that is, calls `model.…` and sends `view.…`. After every saved change it rings the bell, so every
  open `/events` connection says `changed`. It serves only files inside `page/`.
- **Model** (`model.py`): the rules, and the database: `users`, `sessions`, `posts` (replies, reposts
  and quotes are posts too), `likes`, `follows`, `uploads`, `post_tags`, `bookmarks`, `notifications`,
  `messages`. A name is kept once, in `users`; everything else points at it by id. Never store a
  password or a session token, only their hashes. Bookmarks, notifications and messages are private:
  every query for them is about the logged-in person's own.
- **View** (`view.py`): one `…_to_json` function for each kind of answer. It does not decide anything.

## How to run it

- `make run`, then open <http://localhost:8010>. Press Ctrl+C to stop.
- A timeline with made-up people: `make reset seed`. They all have the password `timeline123`.
- Made-up activity for a real account (followers, likes, replies, mentions, messages, bookmarks):
  `make welcome NAME=Alex`.
- Start again with an empty timeline: `make reset` (deletes the database and the uploaded pictures).
- See what is saved: `sqlite3 with-backend/timeline.db '.tables'`

It needs only `python3` (3.9 or newer). Do not add libraries, packages or a build step. The page's
JavaScript uses modules (`import`), which browsers load by themselves.
Write code that runs on Python 3.9: no `match` statements, and no `X | Y` in type hints.

## How to test it

`make test`. Every test must pass before and after a change. A new feature gets a new test in
`with-backend/test_server.py`. The tests lower `model.PASSWORD_ROUNDS` so they stay fast; keep doing
that in any new test that signs people up.

## The one rule

**Keep the three parts separate: the controller in `server.py`, the model in `model.py`, the view in
`view.py`. A new rule goes in the model.** The controller does not check rules and does not touch the
database. The view does not decide anything. If a feature needs a new rule, write it in the model, and
check it in the page too, because the page and the server must agree. The server always checks, even
when the page already did, because a user can change anything that runs on their own device.
Who is asking comes from the session cookie, never from the request body. Everything a user wrote is
put on the page with `textContent`, never `innerHTML`.
