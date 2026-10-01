# Design doc — Timeline (Class 9 and 10 demo, and homework)

*Every name and example row here is made up.*

## 1. The problem

The architecture sessions need one small product the room can watch, open and change all
afternoon. Timeline is a generic Twitter-like app: people post short messages, and everyone's
posts appear on one timeline. It shows why a backend exists: two people on one app, where a version
that keeps everything in the page cannot share a post, and the same app with a backend can.

It is also the **homework repository**. After the architecture sessions each student clones it, asks
their agent to explain its architecture (which file is the controller, the model, the view, and
where the data lives), and then adds one feature to it, with a test. So the code has to be small
enough for a beginner's agent to explain in full, and laid out so that the three parts are obvious
from the file names alone.

## 2. Not in this version

- No accounts, passwords or sign-in. Each window types a display name.
- No follows, likes, replies, deleting or editing. The sessions ask the students to design the data
  for follows and likes, and the homework asks them to add one of these.
- No realtime connection (no WebSockets). The page asks for new posts once a second.
- Nothing reachable from another machine. The server listens on `127.0.0.1` only.
- No Twitter or X names, logos or look. It is a generic app of that kind.
- No libraries, no install, no build step.

## 3. Screens

One screen, the same in both versions:

- **The timeline.** A name field at the top, a *What is happening?* box with a live count
  (*x / 280*) and a **Post** button, and the timeline below it, newest first (author, text, time).
  Its one job: show everyone's posts, and take a new one.

Large type and high contrast, because it is read from the back of the room on a projector.

## 4. The three parts

| Part | `page-only/` | `with-backend/` |
|---|---|---|
| **Frontend** | `index.html` · `style.css` · `app.js` | the same three files; `app.js` talks to the server instead of the browser |
| **Backend** | none: the rules run in `app.js` | `server.py`, Python 3 standard library (`http.server`), written in three labelled parts: **controller · model · view** |
| **Data** | the browser's `sessionStorage` | `timeline.db`, one SQLite file, created by the server when it starts |

**Technologies, and why each one.**

- **Plain HTML, CSS and JavaScript.** It is what the students have written all term, and the
  session's *The frontend has an inside too* shows these exact three files.
- **Python 3 standard library only** (`http.server`, `sqlite3`, `json`). Python ships on the
  classroom Mac (3.9.6 checked), so there is nothing to install, and the course's taught examples
  are already Python. The code avoids anything newer than 3.9.
- **SQLite.** One file, no server of its own, and the `sqlite3` command ships on the Mac too, so
  *Open the store* is one command. Supabase is kept for *Guided integration*.
- **Polling, once a second.** `fetch('/posts?after=<last id>')` on a timer. It is the simplest
  thing that works, and it is exactly what the receive trace draws: the second window asks
  *anything new?*
- **`sessionStorage`, not `localStorage`, for the page-only version.** `localStorage` is what the
  students' own pages used, but two normal windows of one browser share it, so the page-only version
  can look shared and the demo fails in front of the room. `sessionStorage` belongs to one window,
  which is what a second person's phone would have, and it still survives a reload. The slide's
  wording is *remembers (in this window only)*. A private window is still used.

**The seams.**

| Request | What goes in | What comes out |
|---|---|---|
| `POST /posts` | `{"author": "Aiko", "text": "the library is open late tonight"}` | the saved post, with its `id` and `posted_at` · or `400` with the rule it broke |
| `GET /posts?after=12` | the last `id` this window has | every post with a larger `id`, oldest first |
| `GET /` and the three files | nothing | the page |

**The model's rules:** text is not empty after trimming · text is at most 280 characters · author
is not empty, at most 40 characters. The server checks them even though the page checks them too,
because a user can change anything that runs on their own device.

## 5. The data model

One table:

| `posts` | |
|---|---|
| `id` | integer, primary key, given by SQLite |
| `author` | text, the display name |
| `text` | text |
| `posted_at` | text, `HH:MM`, local time |

Example rows: `1 · Aiko · the library is open late tonight · 15:42` · `2 · Ben · thanks! · 15:42`.

**This is the session's first bad model, on purpose.** The author's name is copied into every post.
For a demo with two made-up people and no renaming, that is fine. It gives *Bad model 1* a callback
the room has just seen: *the app I showed you does exactly this; for a demo, fine; for a real app
with millions of people, not.*

## 6. Adversarial review

*To be run: a checker agent reviews sections 1–5, and every objection is recorded here with its
decision.*

## 7. Build or borrow

Everything is built: it is a teaching demo, and building the store yourself is what *Build vs. buy*
later compares with buying it.

---

## As a homework repository

- **`AGENTS.md`** says, in plain words, what each file's one job is, how to run it and how to test
  it, and one rule: *keep the three parts of `server.py` separate; a new rule goes in the model.*
  Codex, Claude Code and Antigravity all read it.
- **`Makefile`**, because every course project has one: `make run` starts the server, `make test`
  runs the checks, `make reset` deletes `timeline.db`.
- **`README.md`** carries the homework: (1) ask your agent to explain the architecture, and write
  down which file is the controller, the model and the view; (2) pick one feature from the list and
  add it, with a test; (3) say which parts changed and why. The list: *follow someone, and a
  following timeline* · *like a post, with a count* · *reply to a post* · *delete your own post* ·
  *edit your own post*. Each touches a different set of parts, which is the point. Pictures are left
  out on purpose: they need a second kind of storage for the files, which is a lesson of its own.
- The repository is published on its own, as `kreativitea/anyone-can-build-timeline`, so students
  can fork and clone it. The source is `demos/timeline/` in the course repository, because the
  Class 10 deck reads `server.py` and `style.css` from there; a change is made there first and
  then copied to the published repository.

## Files

```
demos/timeline/
  DESIGN.md
  README.md            how to run it, the two-window setup, and the homework
  AGENTS.md            what each file does, for the student's agent
  Makefile             make run · make test · make reset
  page-only/           open index.html; nothing to start
    index.html  style.css  app.js
  with-backend/        python3 server.py, then localhost:8009
    index.html  style.css  app.js
    server.py          controller · model · view, labelled
    test_server.py     unittest: the rules, save, and "after"
```

`timeline.db` is created next to `server.py` and is git-ignored. Deleting it resets the demo.

## Checks

- `make test`: an empty post is refused, a long one is refused, a saved post comes back with an
  `id`, and `after` returns only newer posts; one round trip through the real server.
- By hand, in a browser: two windows, a post from each, the rows opened with `sqlite3`.
- The page-only version in two normal windows: the second window stays empty.
- Screenshots of both demo moments and of the rows go in `lectures/class-09/assets/` as the fallback.
