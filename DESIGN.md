# Design doc — Timeline, the advanced version

*Every name and example row here is made up.*

This is the advanced copy of Timeline. The simple version, [anyone-can-build-timeline](https://github.com/Compiledex/anyone-can-build-timeline), has one screen and no
accounts. This version is a small social app in the familiar three-column layout, with accounts,
pictures, replies, reposts and quotes, likes and bookmarks, #tags, @mentions and search, follows,
notifications, private messages and live updates, in a look based on the Kansai Gaidai Asian Studies
Program site.

---

*The product spec*

## 1. The problem

A timeline is useful when each post really belongs to the person who wrote it, when you can find the
people and topics you care about, when you hear about what happens to your posts, and when news
arrives without waiting. The simple version shows why a backend exists. This version shows what a
backend needs once there are real people: knowing who is asking, keeping private things private, and
being careful with files people send.

## 2. Not in this version

- No page-only version: without a server there can be no accounts, messages or live updates.
- No password reset, no e-mail, no changing your name, no blocking or muting.
- No limit on how often someone can try a password, and no HTTPS. Both would be needed before going
  online; the server listens on `127.0.0.1` only.
- No video, and one picture per post. No descriptions (alt text) written by the poster.
- No libraries, no install, no build step. The fonts come from Google Fonts; without internet the
  page uses the computer's own fonts and works the same.

## 3. Screens

Three columns: the **menu** (logo, Home, Explore, Notifications, Messages, Bookmarks, Profile, the
Post button, and who is logged in), the **screen** in the middle under a sticky header (a "／"
breadcrumb, the title with a short thick bar under it, and tabs), and the **sidebar** (search,
"What's happening", "Who to follow"). On a tablet the menu shows icons only and the sidebar goes; on
a phone the menu is a bar at the bottom. The address says which screen, so Back works:

| Address | Screen |
|---|---|
| `#/`, `#/following` | **Home**: the post box, then everyone's posts, or only yours and the people you follow |
| `#/post/12` | **A post**: the posts it answers above it, the post, its replies below |
| `#/@Ben`, `#/@Ben/replies` | **A profile**: banner, picture, bio, numbers, Follow / Message / Edit profile; posts or replies |
| `#/explore`, `#/explore/%23kyoto` | **Explore**: search posts, people and #tags; trends when nothing is searched |
| `#/notifications` | **Notifications**: who liked, reposted, quoted, replied, mentioned or followed; new ones on a pale box |
| `#/messages`, `#/messages/@Ben` | **Messages**: your conversations; one conversation as speech bubbles |
| `#/bookmarks` | **Bookmarks**: the posts you saved |

A post card: round avatar, name (EB Garamond) · short time ("5m", "2h", "30 Sep"), the words with
#tags, @names and web addresses as links, a picture, a quoted post in a box, and a row of icons:
💬 reply, 🔁 repost or quote, ♡ like, 🔖 bookmark, each with its count. Your own posts have "⋯" with
Edit and Delete. A repost shows the post it shares with "Ben reposted" above it. Writing (a post,
reply, quote or edit), logging in, and editing your profile happen in windows (`<dialog>`). Visitors
can read everything and get a navy bar at the bottom to log in or sign up.

**The look**, measured from the site's own stylesheets: deep blue `#0a5181` on white, thin `#dbdbdb`
lines, pale blue-grey `rgba(128, 150, 183, 0.2)` boxes, numbers in EB Garamond and `#3b84b0`, pill
buttons, EB Garamond for titles and names, Roboto and Noto Sans JP for text. Dark mode, profile
banners and the visitor bar use the site's navy `#0f2646` with gold `#f8d491`. The logo is our own:
結 ("to tie together") in gold on navy. The university's logo is not used: on a page with a log-in
box, an official logo would look like an official university service.

---

*The engineering design*

## 4. The parts

```
the browser                              the server                                   the store
page/index.html · style.css · js/*.js ── server.py ── model.py ── view.py ──────────  timeline.db
   a request, with the session cookie ▶    controller   rules      JSON               uploads/
   ◀ the answer                                                                       (pictures)
   ◀ "changed" (one open connection, /events)
```

| Part | Files |
|---|---|
| **Frontend** (runs on the user's device) | `page/index.html`, `page/style.css`, and `page/js/`: `main` (start, address, live updates, buttons), `state` (what the window knows), `api`, `screens`, `render`, `dialogs`, `pictures`, `format`, `icons` |
| **Controller** | `server.py`: reads each request, asks the model, sends the view's answer, rings the bell |
| **Model** | `model.py`: every rule; the only code that touches the database and the uploads folder |
| **View** | `view.py`: one `…_to_json` for each kind of answer |
| **Data** | `timeline.db` (SQLite, ten tables) and `uploads/`, both made by the server, not in git |
| **Made-up data** | `seed.py`, which fills an empty timeline through the model |

**Technologies, and why each one.**

- **Plain HTML, CSS and JavaScript modules.** No framework and no build step: the browser loads the
  modules by itself. The page keeps what it knows in `state.js` and draws each screen from it, again
  after every change. Things you type (the post box, the search box, the message box) stay outside
  the part that is drawn again, so a live update never wipes them out.
- **Python 3 standard library only.** `http.server`, `sqlite3`, `json`, `hashlib`, `hmac`, `secrets`,
  `http.cookies`, `re`, `threading`. Nothing to install. Nothing newer than Python 3.9.
- **PBKDF2 for passwords** (SHA-256, 600,000 rounds, a random salt for each password), and a
  **session cookie** (`HttpOnly`, `SameSite=Strict`, 30 days) whose token is kept only as a SHA-256 hash.
- **Server-Sent Events for live updates.** Each window keeps one connection open to `/events`. After
  any saved change the controller rings a bell (a `threading.Condition`), and every connection sends
  `data: changed`; the page then fetches what is new with the ordinary requests.
- **Pictures as files**, not in the database: the database keeps a row with a random file name.

**The interfaces.** Every change needs a login (`401` without one). A broken rule is `400` with the
reason; something that does not exist is `404`.

| Request | What goes in | What comes out |
|---|---|---|
| `POST /signup`, `POST /login` | `{"name", "password"}` | as `GET /me`, and the session cookie |
| `POST /logout` | nothing | as `GET /me` for nobody, and the cookie removed |
| `GET /me` | the cookie | name, bio, avatar, the names you follow, unread notifications and messages |
| `PUT /me` | `{"bio"}` and/or `{"avatar_id"}` (an upload, or `null`) | as `GET /me` |
| `GET /people` | nothing | everyone's name and picture, for avatars |
| `GET /users?name=Ben` | the cookie, if any | name, bio, avatar, joined, posts, followers, following, `you_follow` |
| `POST`, `DELETE /follows` | `{"name"}` | as `GET /me` |
| `POST /uploads` | the picture itself as the body | `{"id", "url"}` |
| `GET /uploads/…` | nothing | the picture, with `nosniff` and `Content-Security-Policy: default-src 'none'` |
| `GET /posts?after=12` | the last id this window has | every newer post (replies, reposts and quotes too), oldest first |
| `POST /posts` | `{"text"}`, and `reply_to`, `quote_of` or `picture_id` | the saved post |
| `PUT /posts`, `DELETE /posts` | `{"post_id", "text"}`, `{"post_id"}` | the edited or deleted post |
| `GET /changes` | nothing | every edited or deleted post |
| `POST`, `DELETE /reposts` | `{"post_id"}` | the repost (deleted, when undone) |
| `GET`, `POST`, `DELETE /likes` | `{"post_id"}` for a change | every post's like count, and `you_liked` |
| `GET`, `POST`, `DELETE /bookmarks` | `{"post_id"}` for a change | `{"post_ids"}`: your own, latest saved first |
| `GET /search?q=` | `#tag`, or words | `{"post_ids", "people"}` |
| `GET /sidebar` | the cookie, if any | `{"trends", "suggestions"}` |
| `GET /notifications`, `POST /notifications/read` | nothing | your own notifications; `/read` answers as `GET /me` |
| `GET /messages`, `GET /messages?with=Ben` | nothing | your conversations; or one, oldest first |
| `POST /messages`, `POST /messages/read` | `{"to", "text"}`, `{"with"}` | the message; `/read` answers as `GET /me` |
| `GET /events` | nothing; the connection stays open | `data: hello`, then `data: changed` after each change |
| `GET /`, `GET /js/…`, `GET /style.css` | nothing | the page; only files inside `page/` are ever sent |

**The model's rules.**
- *Accounts:* a name is 1 to 40 letters (any language), numbers or `_`, unique whatever its capitals;
  a password is 8 to 200 characters; a wrong name and a wrong password get the same answer; a bio is
  at most 160 characters.
- *Posts:* 1 to 280 characters after trimming (a post with a picture may have none); only the author
  edits or deletes; a deleted post cannot be liked, answered, quoted, reposted, saved or edited; a
  reply, a quote and a repost name a post that exists; liking, answering or quoting a repost acts on
  the original; a repost has no words to edit; a post answers a post or quotes one, not both.
- *Once each:* a like, a repost, a follow, a bookmark, a notification.
- *Pictures:* JPEG, PNG, GIF or WebP, known by their first bytes, never by the file's name; SVG is
  refused because it can hold code; at most 2 MB; used once, and only by the person who uploaded it.
- *Private things:* every query for bookmarks, notifications and messages is about the logged-in
  person's own. You cannot follow or message yourself. A message is 1 to 1000 characters.
- *Notifications* are made inside the action itself (a like and its notification are saved
  together), never for your own actions, and taken back when the action is undone.

The page checks some of these too, so that people do not wait for an answer; the server always
checks, because a user can change anything that runs on their own device.

## 5. The data model

Ten tables. Each fact is kept once: a name lives only in `users`, and every other table points at it
by number. Counts (likes, reposts, followers, unread) are never stored; they are worked out from the
rows when someone asks, so they cannot drift.

| Table | Columns | Notes |
|---|---|---|
| `users` | `id`, `name` (unique, `COLLATE NOCASE`), `password_hash`, `joined_at`, `bio`, `avatar_id` → `uploads` | never the password |
| `sessions` | `token_hash` (primary key), `user_id`, `expires_at` | never the token |
| `posts` | `id`, `author_id`, `text`, `posted_at`, `reply_to` → `posts`, `quote_of` → `posts`, `repost_of` → `posts`, `picture_id` → `uploads`, `edited_at`, `deleted_at` | a reply, a quote and a repost are posts too |
| `likes` | `post_id`, `user_id` | primary key: the pair |
| `follows` | `follower_id`, `followed_id` | primary key: the pair; `CHECK` nobody follows themselves |
| `uploads` | `id`, `owner_id`, `file_name` (random, unique), `content_type`, `uploaded_at` | the file is in `uploads/` |
| `post_tags` | `post_id`, `tag` (small letters) | primary key: the pair |
| `bookmarks` | `user_id`, `post_id`, `saved_at` | primary key: the pair |
| `notifications` | `id`, `user_id`, `actor_id`, `kind`, `post_id`, `created_at`, `read_at` | `CHECK` on `kind`; unique on (user, actor, kind, post) |
| `messages` | `id`, `sender_id`, `receiver_id`, `text`, `sent_at`, `read_at` | `CHECK` nobody messages themselves |

Rules that the database keeps as well as the model, so that even code that skips the model cannot
break them: unique names; one like, follow and bookmark per pair; one live repost per person and post
(a *partial* unique index: unique only among reposts that are not deleted, so a repost can be undone
and done again); no following or messaging yourself; one notification per thing told.

A delete erases a post's words, picture, likes, tags, bookmarks and notifications, but keeps its row:
other people's replies point at it. An undone repost is a repost row marked deleted.

A `timeline.db` from the previous advanced version is kept: when the server starts, it adds the
missing columns and tables, empty, and finds the #tags of the posts already there.

## 6. How I will know it works

1. Every rule in section 4 has a test that breaks it and is refused, and one that keeps it.
2. Nobody sees someone else's bookmarks, notifications or messages, even by asking directly.
3. A file that is not a real picture is refused, and no address leads outside `page/` or
   `uploads/` (`/../model.py`, `/uploads/../timeline.db`).
4. Every saved change makes every open `/events` connection say `changed`; a refused one says nothing.
5. **By hand, in two browsers** (one private, so it can be someone else): post, reply, repost,
   like and message from one, and see the other change at once; check the layout at phone width.

Sentences 1 to 4 are checked by `make test`. Sentence 5 is browser behaviour.

---

## 7. Adversarial review

| Objection | About | Decision | Why | What changed |
|---|---|---|---|---|
| Use the university's real logo. | product | reject | It is their trademark, and on a page with a log-in box it would look like an official service. | Our own logo, 結, in the site's colours. |
| A picture's type could be trusted from its name or its Content-Type. | security | reject | Both are written by the sender. | The model reads the first bytes. |
| SVG pictures would be nice. | security | reject | An SVG can hold a script. | Refused. |
| A picture opened on its own could run as a page. | security | accept | Defence in depth costs two headers. | `nosniff` and `Content-Security-Policy: default-src 'none'`. |
| Notifications could be counted on the page. | design | reject | The page cannot see other people's likes of your posts made while you were away. | A `notifications` table, filled by the model. |
| A repost could be a separate table. | design | reject | As a post row it gets its place in the timeline and live updates for free. | `posts.repost_of`. |
| Drawing the whole screen again after every change is wasteful. | design | accept, as a limit | Simple and correct for a class; boxes you type in are kept outside it. | Written down here. |
| Every window gets every post, and the Following tab filters on the page. | design | accept, as a limit | Fine for a class; a big site would page and filter on the server. | Written down here. |
| Each open window holds one connection; a browser allows about six to one site over HTTP/1.1. | design | accept, as a limit | HTTP/2 would remove it. | Written down here. |

## 8. Build or borrow

- **Built:** the page, the server, the data model, the icons and the made-up data.
- **Borrowed:** Python and its standard library, SQLite, the browser (`EventSource`, `<dialog>`,
  modules), and the fonts EB Garamond, Roboto, Noto Sans JP and Noto Serif JP from Google Fonts.

---

## Files

```
README.md            what it is, how to run it
AGENTS.md            what each file does, for an AI agent working here
DESIGN.md            this document
Makefile             make run · make test · make reset · make seed
.claude/launch.json  starts the server from the Claude Code desktop app
with-backend/        make run, then http://localhost:8010
  server.py          the controller (the file you start)
  model.py           the model: the rules and the database
  view.py            the view: the JSON
  seed.py            made-up people, posts and messages
  test_server.py     unittest: every rule, privacy, pictures, live updates, real round trips
  page/              everything the browser gets, and nothing else
    index.html  style.css
    js/  main  state  api  screens  render  dialogs  pictures  format  icons
```

`timeline.db` and `uploads/` are created next to `server.py` and are git-ignored. `make reset`
deletes both.
