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

## The two-window setup (in class)

1. Open the app in one normal window. Type the name **Aiko**.
2. Open it again in a **private window** (Chrome: Incognito, Safari: Private Window). Type the name
   **Ben**. Put the two windows side by side.
3. Post from each window.

- **With the backend**: a post from one window appears at the top of the other window within one
  second.
- **Page-only**: a post never appears in the other window. Each window has only its own posts.

Open a new window. Do not duplicate a tab: a duplicated tab copies the first tab's `sessionStorage`.

To show what happens when the backend is gone, stop the server with **Ctrl+C**. Both windows say
*Cannot reach the server*. Start it again with `make run`, and they start working again by themselves.

## Open the store

The backend keeps every post in one file, `with-backend/timeline.db`. To see what is inside:

```
sqlite3 with-backend/timeline.db 'select * from posts'
```

Each line is one post: `id|author|text|posted_at`.

To start again with an empty timeline, stop the server and run `make reset`.

## Check it

```
make test
```

This runs the checks in `with-backend/test_server.py`. They test the rules (an empty post and a
post over 280 characters are refused), saving a post, asking only for newer posts, and one full
trip through the real server.

## Homework

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

Each feature changes a different set of parts. That is the point of the exercise.

Keep the three parts of `server.py` separate. A new rule goes in the model. `make test` must pass
when you finish.
