# Timeline, the advanced version

A small Twitter-like app. People sign up, post short messages, reply, like, edit and delete their
own posts, follow each other, and open each other's profiles. Every open window sees every change
at once. The look follows the Kansai Gaidai Asian Studies Program site: deep blue on white, EB
Garamond for names, navy and gold for profiles.

This is the advanced copy of Timeline. The simple version (no accounts, a page-only version, a
check for news every second) lives in its own folder, kept as it was, so you can compare the two.

You need a web browser and `python3`, version 3.9 or newer. A Mac already has it. There is nothing
to install.

## Run it

```
make reset seed
make run
```

Then open <http://localhost:8010>. `make reset seed` fills the timeline with 12 made-up students and
three days of posts, replies, likes and follows. Log in as any of them, for example **Aiko**, with
the password **timeline123**, or sign up with your own name.

Each new post prints one line in the terminal. To stop the server, press **Ctrl+C**.

The simple version runs on port 8009, so both can run at the same time.

## See it work

- **Accounts.** Anyone can read the timeline. To post, reply, like or follow, log in. Only the
  author sees **Edit** and **Delete**, and the server refuses everyone else, even if they send the
  request without the page.
- **Profiles.** Click a name. The address becomes `#/@Ben`, so the Back button works.
- **Follows.** Press **Follow** on a profile, then open the **Following** tab.
- **Live updates.** Open the app in two browsers, one of them a **private window** (it has its own
  cookies, so it can be logged in as someone else). Post or like in one, and the other changes at
  once. Stop the server: both say *Cannot reach the server*. Start it: both recover by themselves.

## Open the store

Everything is in one file, `with-backend/timeline.db`, in five tables: `users`, `sessions`,
`posts`, `likes` and `follows`.

```
sqlite3 with-backend/timeline.db 'select id, name, joined_at from users; select * from follows'
```

Look at `password_hash` in `users`: it starts with `pbkdf2_sha256$600000$`, then a random salt, then
the hash. The password itself is not there, and cannot be worked out from it.

To start again with an empty timeline, stop the server and run `make reset`.

## Check it

```
make test
```

This runs the checks in `with-backend/test_server.py`: accounts and passwords, posts, likes,
replies, edits, deletes, profiles, follows, live updates, the made-up data, and full trips through
the real server.

## Read more

`DESIGN.md` explains every request, table and rule, and why each technology was chosen.
`AGENTS.md` is for an AI agent working here. Keep the three parts of `server.py` separate, and put
a new rule in the model. `make test` must pass when you finish.
