# Timeline

A small app where people post short messages. Everyone's posts appear on one timeline, newest
first. It comes in two versions with the same screen:

- **`page-only/`**: everything runs in the browser. There is no server. Each window keeps its own
  posts, so nothing is shared.
- **`with-backend/`**: the page sends each post to a small Python server, which saves it in a
  database. Every window asks the server for new posts once a second, so every window sees every post.

The difference between the two is the reason a backend exists.

You need a web browser. For the backend version you also need `python3`, version 3.9 or newer.
A Mac already has it. There is nothing to install.

## Get your own copy

On GitHub, press **Fork** at the top of this page. That makes a copy under your own account. Then
clone your copy and go into its folder (put your GitHub name where it says `YOUR-NAME`):

```
git clone https://github.com/YOUR-NAME/anyone-can-build-timeline.git
cd anyone-can-build-timeline
make test
```

Every check should pass. If one does not, ask your agent why before you change anything.

## Run the page-only version

Open `page-only/index.html` in a browser. That is all.

## Run the backend version

```
make run
```

Then open <http://localhost:8009>. To stop the server, press **Ctrl+C** in the terminal.

Without `make`, the same thing is: `cd with-backend`, then `python3 server.py`.

In the Claude Code desktop app, `.claude/launch.json` starts the same server and opens it for you.

## See the difference

Open the app in two windows side by side, one of them a **private window** (Chrome: Incognito,
Safari: Private Window), and post from each. With the backend, a post from one window appears in the
other within a second. Page-only, it never does: each window keeps only its own posts. Open a new
window rather than duplicating a tab, because a duplicated tab copies the first tab's
`sessionStorage`.

Stop the server with **Ctrl+C**, and both windows say *Cannot reach the server*. Start it again with
`make run`, and they recover by themselves.

## Open the store

The backend keeps everything in one file, `with-backend/timeline.db`, in two tables: `users`,
with each person once, and `posts`, where each post points at its author by number. To see what is
inside:

```
sqlite3 with-backend/timeline.db 'select * from users; select * from posts'
```

A user line is `id|name`. A post line is `id|author_id|text|posted_at`: the `author_id` is the
`id` of a user.

To start again with an empty timeline, stop the server and run `make reset`.

## Check it

```
make test
```

This runs the checks in `with-backend/test_server.py`. They test the rules (an empty post and a
post over 280 characters are refused), saving a post, asking only for newer posts, and one full
trip through the real server.

## Things to try

1. **Explain it.** Ask your AI agent to explain the architecture of this repository. Write down, in
   your own words, which file or part is the **controller**, which is the **model**, which is the
   **view**, and where the data lives.
2. **Add one feature, with a test.** Pick one from this list:
   - follow someone, and show a "following" timeline
   - like a post, with a count
   - reply to a post
   - delete your own post
   - edit your own post
3. **Say what changed and why.** Which parts did your feature change: the page, the controller, the
   model, the view, the database? Why those parts, and not the others?

Each feature changes a different set of parts.

Keep the three parts of `server.py` separate. A new rule goes in the model. `make test` must pass
when you finish.
