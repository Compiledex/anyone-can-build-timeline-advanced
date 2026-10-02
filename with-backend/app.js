// Timeline, the version WITH a backend.
//
// This page keeps nothing itself. It sends each new post, reply, edit, delete and like
// to the server (server.py), and every second it asks the server three things:
// "any new posts?", "how many likes?" and "which posts were edited or deleted?"
// Because every window asks the same server, every window sees the same timeline.

const MAX_TEXT = 280;
const CANNOT_REACH = "Cannot reach the server. Trying again every second.";

const authorBox = document.getElementById("author");
const textBox = document.getElementById("text");
const countLine = document.getElementById("count");
const statusLine = document.getElementById("status");
const timeline = document.getElementById("timeline");
const postForm = document.getElementById("post-form");
const modeLine = document.getElementById("mode-line");
const modeText = document.getElementById("mode-text");
const cancelButton = document.getElementById("cancel-mode");
const submitButton = document.getElementById("submit-button");

// The id of the newest post this window has shown. 0 means "none yet".
let lastId = 0;

// Each post on the screen, found by its id: its author, and the parts that can change.
const shownPosts = new Map();

// What the box is for right now: a new post, a reply to a post, or an edit of a post.
let mode = { kind: "post", postId: null };

// Put one post on the screen: a new post at the top, a reply under its post.
function showPost(post) {
  // Skip a post this window already shows.
  if (post.id <= lastId) {
    return;
  }
  lastId = post.id;

  const item = document.createElement("li");
  item.className = "post";

  const author = document.createElement("span");
  author.className = "post-author";
  author.textContent = post.author;

  const time = document.createElement("span");
  time.className = "post-time";
  time.textContent = post.posted_at;

  const edited = document.createElement("span");
  edited.className = "post-edited";

  const text = document.createElement("p");
  text.className = "post-text";

  const like = smallButton("like-button", () => toggleLike(post.id, like));
  const reply = smallButton("reply-button", () => startReply(post.id));
  reply.textContent = "Reply";
  const edit = smallButton("edit-button", () => startEdit(post.id));
  edit.textContent = "Edit";
  const remove = smallButton("delete-button", () => deletePost(post.id));
  remove.textContent = "Delete";

  const buttons = document.createElement("div");
  buttons.className = "post-buttons";
  buttons.append(like, reply, edit, remove);

  const replies = document.createElement("ol");
  replies.className = "replies";

  // textContent, never innerHTML: a post is shown as words, so it cannot run code on the page.
  item.append(author, time, edited, text, buttons, replies);

  const parent = shownPosts.get(post.reply_to);
  if (parent) {
    parent.replies.append(item);   // replies go under their post, oldest first, like a conversation
  } else {
    timeline.prepend(item);        // posts go on top, so the newest is always first
  }

  shownPosts.set(post.id, { author: post.author, item, text, edited, buttons, like, edit, remove, replies });
  showLikeCount(like, 0, false);
  showText(post);
  showOwnButtons(post.id);
}

function smallButton(className, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "small-button " + className;
  button.addEventListener("click", onClick);
  return button;
}

// Show a post's text, and "edited" with the time if it was edited.
// A deleted post keeps its place, so its replies stay under it, but shows no words and no buttons.
function showText(post) {
  const shown = shownPosts.get(post.id);
  if (!shown) {
    return;
  }
  if (post.deleted_at) {
    shown.item.classList.add("deleted");
    shown.text.textContent = "This post was deleted.";
    shown.edited.textContent = "";
    shown.buttons.hidden = true;
    if (mode.postId === post.id) {
      cancelMode();   // the post being answered or edited is gone
    }
    return;
  }
  shown.text.textContent = post.text;
  shown.edited.textContent = post.edited_at ? "edited " + post.edited_at : "";
}

// The Edit and Delete buttons show only on posts by the name in the box.
// The server checks this again: a name can edit and delete only its own posts.
function showOwnButtons(postId) {
  const shown = shownPosts.get(postId);
  const own = shown.author === authorBox.value.trim();
  shown.edit.hidden = !own;
  shown.remove.hidden = !own;
}

// Show a number of likes on a Like button: ♥ if you liked the post, ♡ if not.
function showLikeCount(button, count, youLiked) {
  button.textContent = (youLiked ? "♥ " : "♡ ") + count;
  button.classList.toggle("liked", youLiked);
  button.setAttribute("aria-pressed", youLiked);
  button.setAttribute("aria-label", "Like this post. " + count + " likes.");
}

// Show the like counts from the server. A post that is not in the list has no likes.
function showLikes(counts) {
  const byPost = new Map();
  for (const count of counts) {
    byPost.set(count.post_id, count);
  }
  for (const [postId, shown] of shownPosts) {
    const count = byPost.get(postId) || { likes: 0, you_liked: false };
    showLikeCount(shown.like, count.likes, count.you_liked);
  }
}

function showStatus(words) {
  statusLine.textContent = words;
}

// The live count under the box: "x / 280".
function updateCount() {
  const length = textBox.value.length;
  countLine.textContent = length + " / " + MAX_TEXT;
  countLine.classList.toggle("too-long", length > MAX_TEXT);
}

// Change what the box is for: "post", "reply" or "edit".
function setMode(kind, postId) {
  mode = { kind: kind, postId: postId };
  modeLine.hidden = kind === "post";
  if (kind === "reply") {
    modeText.textContent = "Replying to " + shownPosts.get(postId).author;
    submitButton.textContent = "Reply";
  } else if (kind === "edit") {
    modeText.textContent = "Editing your post";
    submitButton.textContent = "Save";
  } else {
    submitButton.textContent = "Post";
  }
}

function startReply(postId) {
  if (mode.kind === "edit") {
    textBox.value = "";   // the box held the post being edited, not a reply
  }
  setMode("reply", postId);
  updateCount();
  textBox.focus();
}

function startEdit(postId) {
  setMode("edit", postId);
  textBox.value = shownPosts.get(postId).text.textContent;
  updateCount();
  textBox.focus();
}

function cancelMode() {
  setMode("post", null);
  textBox.value = "";
  updateCount();
  showStatus("");
}

// Send something to the server. Returns the server's answer,
// or null after showing why it did not work.
async function send(method, path, data) {
  try {
    const response = await fetch(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });
    const answer = await response.json();
    if (!response.ok) {
      // The server refused. It says which rule was broken.
      showStatus(answer.error);
      return null;
    }
    showStatus("");
    return answer;
  } catch (error) {
    showStatus(CANNOT_REACH);
    return null;
  }
}

// Ask the server for every post newer than the last one we have.
async function checkForNewPosts() {
  try {
    const response = await fetch("/posts?after=" + lastId);
    const posts = await response.json();
    // The server sends them oldest first, so a post always comes before its replies.
    for (const post of posts) {
      showPost(post);
    }
    if (statusLine.textContent === CANNOT_REACH) {
      showStatus("");
    }
  } catch (error) {
    showStatus(CANNOT_REACH);
  }
}

// Ask the server how many likes each post has, and which ones the name in the box liked.
async function checkLikes() {
  try {
    const response = await fetch("/likes?name=" + encodeURIComponent(authorBox.value.trim()));
    showLikes(await response.json());
  } catch (error) {
    showStatus(CANNOT_REACH);
  }
}

// Ask the server for every edited or deleted post, and show what it says now.
async function checkChanges() {
  try {
    const response = await fetch("/changes");
    for (const post of await response.json()) {
      showText(post);
    }
  } catch (error) {
    showStatus(CANNOT_REACH);
  }
}

// Ask, wait for the answers, wait one second, then ask again. Forever.
// Posts first, so that every post is on the screen before its likes and changes arrive.
async function keepChecking() {
  await checkForNewPosts();
  await checkLikes();
  await checkChanges();
  setTimeout(keepChecking, 1000);
}

// The Post button: send a new post, a reply, or an edit, depending on the mode.
async function sendPost(event) {
  event.preventDefault();
  const author = authorBox.value;
  const text = textBox.value;

  // A quick check on the page, so the person does not wait for an answer.
  // The server checks the same rules again. Never trust only the screen:
  // anyone can send a request without using this page at all.
  if (text.trim() === "") {
    showStatus("The post must not be empty.");
    return;
  }

  if (mode.kind === "edit") {
    const post = await send("PUT", "/posts", { post_id: mode.postId, name: author, text: text });
    if (!post) {
      return;
    }
    showText(post);
  } else {
    // reply_to is null for a new post, or the id of the post being answered.
    const post = await send("POST", "/posts", { author: author, text: text, reply_to: mode.postId });
    if (!post) {
      return;
    }
  }
  // Saved. Ask for new posts now, instead of waiting for the next second.
  // This also brings in any post from another window that came just before ours.
  cancelMode();
  await checkForNewPosts();
}

// The Like button: like the post, or take the like back if this name already liked it.
async function toggleLike(postId, button) {
  const name = authorBox.value;

  // A quick check on the page. The server checks the same rules again,
  // and only the server can know for sure whether this name already liked this post.
  if (name.trim() === "") {
    showStatus("The name must not be empty.");
    return;
  }

  button.disabled = true;   // so a double-click sends only one request
  const method = button.classList.contains("liked") ? "DELETE" : "POST";
  const counts = await send(method, "/likes", { post_id: postId, name: name });
  if (counts) {
    showLikes(counts);
  }
  button.disabled = false;
}

// The Delete button: ask first, because a deleted post cannot come back.
async function deletePost(postId) {
  if (!confirm("Delete this post? It cannot be undone.")) {
    return;
  }
  const post = await send("DELETE", "/posts", { post_id: postId, name: authorBox.value });
  if (post) {
    showText(post);
  }
}

// A new name in the box: show the Edit and Delete buttons and likes that belong to that name.
function nameChanged() {
  for (const postId of shownPosts.keys()) {
    showOwnButtons(postId);
  }
  if (mode.kind === "edit") {
    cancelMode();   // the post being edited may not belong to the new name
  }
  checkLikes();
}

textBox.addEventListener("input", updateCount);
authorBox.addEventListener("input", nameChanged);
cancelButton.addEventListener("click", cancelMode);
postForm.addEventListener("submit", sendPost);
keepChecking();
