# Timeline, the advanced version

A small social app, in the familiar three columns: a menu on the left, the timeline in the middle,
and what's happening on the right. People sign up and post, with a picture if they like. They reply,
repost and quote, like and bookmark, edit and delete their own posts, use #tags and @mentions,
search, follow each other, get notifications, and send private messages. Every open window sees every
change at once.

The look follows the Kansai Gaidai Asian Studies Program site: deep blue on white, EB Garamond for
titles and names, pale blue-grey boxes, and navy with gold. The logo, 結 ("to tie together"), is our
own; the university's logo is not used.

This is the advanced copy of Timeline. The simple version (no accounts, a page-only version, a check
for news every second) lives in its own folder, kept as it was, so you can compare the two.

You need a web browser and `python3`, version 3.9 or newer. A Mac already has it. There is nothing
to install.

## Run it

```
make reset seed
make run
```

Then open <http://localhost:8010>. `make reset seed` fills the timeline with 12 made-up students and
three days of posts, replies, reposts, quotes, likes, follows, bookmarks and messages. Log in as any of
them, for example **Aiko**, with the password **timeline123**, or sign up with your own name. Then
`make welcome NAME=YourName` gives your account made-up followers, likes, replies, mentions,
messages and bookmarks from the last two hours, so you can see how it feels.

To stop the server, press **Ctrl+C**. The simple version runs on port 8009, so both can run at once.

## See it work

- **Post** with the box on Home, or the Post button. 🖼 adds a picture (JPEG, PNG, GIF or WebP, up to 2 MB).
- Under each post: 💬 reply, 🔁 repost or quote, ♡ like, 🔖 bookmark. Your own posts have a "⋯"
  menu with Edit and Delete. Click a post to open it with its replies.
- **#tags** and **@names** are links. **Explore** searches posts, people and #tags.
- **Profiles**: click a name. Follow, Message, and on your own, Edit profile (bio and picture).
- **Notifications** and **Messages** have a red number for what is new.
- **Live**: open the app in two browsers, one of them a **private window** (it has its own
  cookies, so it can be someone else). Like, post or send a message in one, and the other changes
  at once.

## Open the store

Everything is in `with-backend/timeline.db`, and the pictures in `with-backend/uploads/`.

```
sqlite3 with-backend/timeline.db '.tables'
sqlite3 with-backend/timeline.db 'select kind, post_id, created_at from notifications limit 5'
```

Look at `password_hash` in `users`: it starts with `pbkdf2_sha256$600000$`, then a random salt,
then the hash. The password itself is not there, and cannot be worked out from it.

To start again with an empty timeline, stop the server and run `make reset`.

## Check it

```
make test
```

This runs the checks in `with-backend/test_server.py`: every rule of the model, the pages and pictures
the server will and will not send, privacy (nobody sees someone else's bookmarks, notifications or
messages), live updates, the made-up data, and full trips through the real server.

## Read more

`DESIGN.md` explains every screen, request, table and rule, and why each technology was chosen.
`AGENTS.md` is for an AI agent working here. Keep the controller, model and view in their own files,
and put a new rule in the model. `make test` must pass when you finish.
