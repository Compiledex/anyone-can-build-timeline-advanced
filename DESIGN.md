# Design doc — Timeline, the advanced version

*Every name and example row here is made up.*

This is the advanced copy of Timeline. The simple version, in its own folder, has no accounts: a
window types a name, and anyone can type anyone's name. This version adds real accounts, follows,
profile pages, live updates, a look based on the Kansai Gaidai Asian Studies Program site, and
made-up data so that it looks alive.

---

*The product spec*

## 1. The problem

A timeline is only useful if each post really belongs to the person who wrote it, if you can find the
people you care about, and if news arrives without waiting. The simple version shows why a backend
exists. This version shows what a backend needs once there are real people: knowing who is asking.

## 2. Not in this version

- No page-only version. Without a server there can be no accounts, follows or live updates. The
  simple version still has one.
- No password reset, no e-mail, no changing your name.
- No pictures. A picture needs a second kind of storage for its files, which is a design of its own.
- No limit on how often someone can try a password. It would be needed before going online.
- Nothing reachable from another machine. The server listens on `127.0.0.1` only. Going online
  would also need HTTPS, so that passwords and cookies cannot be read on the way.
- No libraries, no install, no build step. The fonts come from Google Fonts; without internet the
  page uses the computer's own fonts and works the same.

## 3. Screens

One page, with three screens in the address, so the browser's Back button works:

- **Everyone** (`#/`): a **Log in / Sign up** box for visitors, or, for someone logged in, the
  *What is happening?* box with a live count (*x / 280*) and a **Post** button. Then the timeline,
  newest first: author (a link to their profile), time, text, and **♡ Like** with its count,
  **Reply**, and **Edit** and **Delete** on your own posts. Replies sit under their post, oldest
  first. A deleted post shows only *This post was deleted.*, with its replies still under it.
- **Following** (`#/following`): the same, with only your own posts and those of the people you follow.
- **A profile** (`#/@Ben`): the name in gold on navy, when they joined, posts, followers, following,
  a **Follow** button, and every thread they wrote a post or a reply in.

**The look**, measured from the site's own stylesheets: deep blue `#0a5181` on white, thin `#dbdbdb`
lines, `#edf1f4` on hover, pill-shaped buttons, EB Garamond for the title and names, Roboto and Noto
Sans JP for text. Dark mode, and the top of a profile, use the site's navy `#0f2646` with gold
`#f8d491`. Only colours and fonts are borrowed: no logo, no photos.

---

*The engineering design*

## 4. The three parts

```
the browser                          the server                         the store
index.html · style.css · app.js  ──  server.py  ──────────────────────  timeline.db
   a request, with the session cookie ▶   who is this? save this ▶
   ◀ the answer                           ◀ the rows
   ◀ "changed" (one open connection, /events)
```

| Part | Files |
|---|---|
| **Frontend** (runs on the user's device) | `index.html` · `style.css` · `app.js` |
| **Backend** (runs on the server) | `server.py`, Python 3 standard library only, in three labelled parts: **controller · model · view** |
| **Data** (runs on the server) | `timeline.db`, one SQLite file with five tables, created by the server when it starts |
| **Made-up data** | `seed.py`, which fills an empty timeline through the model |

**Technologies, and why each one.**

- **Plain HTML, CSS and JavaScript.** Three files, each with one job: structure, looks, behaviour.
- **Python 3 standard library only.** `http.server`, `sqlite3`, `json`, and for accounts `hashlib`,
  `hmac`, `secrets` and `http.cookies`. Nothing to install. Nothing newer than Python 3.9.
- **PBKDF2 for passwords** (`hashlib.pbkdf2_hmac`, SHA-256, 600,000 rounds, a random salt for
  each password). Slow on purpose: someone who steals the database must spend that work on every guess.
- **A session cookie** (`HttpOnly`, `SameSite=Strict`, 30 days). `HttpOnly`: the page's JavaScript
  cannot read it. `SameSite=Strict`: the browser sends it only to this site, so another site cannot
  make your browser act as you. The database keeps only a SHA-256 hash of each token.
- **Server-Sent Events for live updates.** Each window keeps one connection open to `/events`. After
  any saved change the controller rings a bell (a `threading.Condition`), and every open connection
  sends `data: changed`. The page then fetches what is new with the ordinary requests. The browser's
  `EventSource` reconnects by itself. It is one-way (server to page), which is all this needs, so it
  is simpler than WebSockets.

**The interfaces.** Every request that changes something needs a login, and gets `401` without one.

| Request | What goes in | What comes out |
|---|---|---|
| `POST /signup` | `{"name": "Aiko", "password": "…"}` | `{"name", "following"}`, and the session cookie · or `400` |
| `POST /login` | `{"name": "Aiko", "password": "…"}` | the same · or `400` *Wrong name or password.* |
| `POST /logout` | nothing | `{"name": null, "following": []}`, and the cookie removed |
| `GET /me` | the cookie | who is logged in (or `null`), and the names they follow |
| `GET /posts?after=12` | the last `id` this window has | every post with a larger `id`, oldest first |
| `POST /posts` | `{"text": "…"}`, and `"reply_to": 3` for a reply | the saved post · or `400` / `404` |
| `PUT /posts` | `{"post_id": 3, "text": "…"}` | the edited post · or `400` / `404` |
| `DELETE /posts` | `{"post_id": 3}` | the deleted post: empty `text`, with its `deleted_at` |
| `GET /changes` | nothing | every edited or deleted post, oldest first |
| `GET /likes` | the cookie, if any | `[{"post_id": 3, "likes": 2, "you_liked": true}, …]` |
| `POST /likes`, `DELETE /likes` | `{"post_id": 3}` | every post's likes, as `GET /likes` |
| `GET /users?name=Ben` | the cookie, if any | `{"name", "joined_at", "posts", "followers", "following", "you_follow"}` · or `404` |
| `POST /follows`, `DELETE /follows` | `{"name": "Ben"}` | as `GET /me` |
| `GET /events` | nothing; the connection stays open | `data: hello` at once, then `data: changed` after each change |
| `GET /` and the three files | nothing | the page |

**The model's rules:** a name is 1 to 40 characters and belongs to one account, whatever its
capitals · a password is 8 to 200 characters · a wrong name and a wrong password get the same answer ·
text is 1 to 280 characters after trimming · a like, a reply, an edit and a delete name a post that
exists and is not deleted · you like a post at most once, and take back only your own like · only the
author can edit or delete a post · you cannot follow yourself, or follow someone twice. The page
checks some of these too, so that people do not wait for an answer; the server always checks,
because a user can change anything that runs on their own device.

## 5. The data model

Five tables:

| `users` | |
|---|---|
| `id` | integer, primary key |
| `name` | text, unique whatever its capitals (`COLLATE NOCASE`) |
| `password_hash` | text, `pbkdf2_sha256$rounds$salt$hash`; never the password |
| `joined_at` | text, `2026-10-02 15:42`, local time |

| `sessions` | |
|---|---|
| `token_hash` | text, primary key: the SHA-256 of the token in the cookie |
| `user_id` | integer, foreign key to `users` |
| `expires_at` | text, 30 days after logging in |

| `posts` | |
|---|---|
| `id` | integer, primary key |
| `author_id` | integer, foreign key to `users` |
| `text` | text; empty once deleted |
| `posted_at` | text, `2026-10-02 15:42` |
| `reply_to` | integer, foreign key to `posts` · empty for a post |
| `edited_at`, `deleted_at` | text · empty until it happens |

| `likes` | | | `follows` | |
|---|---|---|---|---|
| `post_id` | foreign key to `posts` | | `follower_id` | foreign key to `users` |
| `user_id` | foreign key to `users` | | `followed_id` | foreign key to `users` |
| primary key | `(post_id, user_id)` | | primary key | `(follower_id, followed_id)`, and `CHECK (follower_id != followed_id)` |

Each fact is kept once. A name lives only in `users`; every other table points at it by number.
Counts (likes, posts, followers) are never stored: they are worked out with `COUNT(*)` when someone
asks, so they cannot drift away from the rows.

Some rules live in the database as well as in the model, so that even code that skips the model
cannot break them: a name is unique, a like and a follow are kept once, and nobody follows themselves.

A delete erases the post's `text` and its likes, but keeps its row: other people's replies point at
it by `reply_to`, and deleting your post should not delete what they wrote.

A `timeline.db` from the simple version has no passwords, so the server refuses it and asks for
`make reset`.

## 6. How I will know it works

1. When someone signs up, the database should hold a hash and not the password, and the cookie
   should be `HttpOnly`. A wrong name and a wrong password should get the same answer.
2. Without a login, every change should get `401`; with one, only the author should be able to
   edit or delete.
3. A like, a follow, and following yourself should be refused the second time, by the model and by
   the database.
4. When anything is saved, every open `/events` connection should say `changed`; a refused request
   should say nothing.
5. **By hand, in two browsers** (one of them a private window, so it has its own cookie): log in as
   two people, post from one, and see it in the other at once. Follow, and see the Following tab
   change. Stop the server, see *Cannot reach the server*, start it, and see the page recover.

Sentences 1 to 4 are checked by `make test`. Sentence 5 is browser behaviour.

---

## 7. Adversarial review

| Objection | About | Decision | Why | What changed |
|---|---|---|---|---|
| Anyone can type anyone's name and delete their posts. | design | accept | It was the simple version's biggest limit. | Accounts with passwords and a session cookie. |
| Keeping session tokens in the database lets a stolen copy log in as anyone. | security | accept | One line of hashing removes the risk. | `sessions` keeps a SHA-256 of each token. |
| "No such user" and "wrong password" tell a stranger which names exist. | security | accept | The answer gives nothing away when it is the same. | One message for both. |
| `aiko` could pretend to be `Aiko`. | design | accept | A name should belong to one person. | `COLLATE NOCASE` on `users.name`. |
| Asking every second is wasteful, and up to a second late. | design | accept | The server knows when something changes. | Server-Sent Events. |
| WebSockets would be more standard. | design | reject | Messages only go one way, and the standard library has no WebSockets. | Nothing. |
| Each open window holds one connection; a browser allows about six to one site over HTTP/1.1. | design | accept, as a limit | Fine for a class; HTTP/2 would remove it. | Written down here. |
| The Following tab should be filtered on the server. | design | reject, for now | Every window already has every post; filtering on the page is simpler. It would need changing for a big site. | Nothing. |

## 8. Build or borrow

- **Built:** the page, the server, the data model and the made-up data.
- **Borrowed:** Python and its standard library, SQLite, the browser's `EventSource`, and the fonts
  EB Garamond, Roboto and Noto Sans JP from Google Fonts.

---

## Files

```
README.md            what it is, how to run it
AGENTS.md            what each file does, for an AI agent working here
DESIGN.md            this document
Makefile             make run · make test · make reset · make seed
.claude/launch.json  starts the server from the Claude Code desktop app
with-backend/        make run, then http://localhost:8010
  index.html  style.css  app.js
  server.py          controller · model · view, labelled
  seed.py            made-up people, posts, likes and follows
  test_server.py     unittest: accounts, posts, likes, replies, edits, deletes, profiles,
                     follows, live updates, the made-up data, real round trips
```

`timeline.db` is created next to `server.py` and is git-ignored. `make reset` deletes it.
