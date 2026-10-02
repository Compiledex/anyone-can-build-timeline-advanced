// Timeline, the PAGE-ONLY version.
//
// Everything happens inside this one browser window. There is no server.
// The rules run here, and the posts and likes are kept in this window's sessionStorage.
//
// Why sessionStorage, and not localStorage?
// localStorage is shared by every normal window of the same browser, so two
// windows could look "shared" when nothing is really shared.
// sessionStorage belongs to one window only, like each person's own phone.
// It survives a reload, but a second window starts empty and never sees
// this window's posts. That is the point of this version.

const MAX_TEXT = 280;
const MAX_AUTHOR = 40;
const STORAGE_KEY = "timeline-posts";
const LIKES_KEY = "timeline-likes";

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

// Each post on the screen, found by its id: its author, and the parts that can change.
const shownPosts = new Map();

// What the box is for right now: a new post, a reply to a post, or an edit of a post.
let mode = { kind: "post", postId: null };

// Read the saved posts from this window. Oldest first.
function loadPosts() {
  try {
    return JSON.parse(sessionStorage.getItem(STORAGE_KEY)) || [];
  } catch (error) {
    return [];
  }
}

function savePosts(posts) {
  sessionStorage.setItem(STORAGE_KEY, JSON.stringify(posts));
}

// Read the saved likes from this window: for each post id, the names that liked it.
// For example { "3": ["Aiko", "Ben"] } means Aiko and Ben liked post 3.
function loadLikes() {
  try {
    return JSON.parse(sessionStorage.getItem(LIKES_KEY)) || {};
  } catch (error) {
    return {};
  }
}

function saveLikes(likes) {
  sessionStorage.setItem(LIKES_KEY, JSON.stringify(likes));
}

// The rules. The backend version keeps the same rules in server.py.
// Each one returns the broken rule, or "" if every rule is kept.
function brokenNameRule(author) {
  if (author === "") {
    return "The name must not be empty.";
  }
  if (author.length > MAX_AUTHOR) {
    return "The name must be 40 characters or fewer.";
  }
  return "";
}

function brokenRule(author, text) {
  const nameProblem = brokenNameRule(author);
  if (nameProblem !== "") {
    return nameProblem;
  }
  if (text === "") {
    return "The post must not be empty.";
  }
  if (text.length > MAX_TEXT) {
    return "The post must be 280 characters or fewer.";
  }
  return "";
}

// The time now, as HH:MM.
function timeNow() {
  const now = new Date();
  const hours = String(now.getHours()).padStart(2, "0");
  const minutes = String(now.getMinutes()).padStart(2, "0");
  return hours + ":" + minutes;
}

// Put one post on the screen: a new post at the top, a reply under its post.
function showPost(post) {
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

  const like = smallButton("like-button", () => toggleLike(post.id));
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
  showText(post);
  showLikes(post.id);
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
  if (post.deleted_at) {
    shown.item.classList.add("deleted");
    shown.text.textContent = "This post was deleted.";
    shown.edited.textContent = "";
    shown.buttons.hidden = true;
    return;
  }
  shown.text.textContent = post.text;
  shown.edited.textContent = post.edited_at ? "edited " + post.edited_at : "";
}

// The Edit and Delete buttons show only on posts by the name in the box.
function showOwnButtons(postId) {
  const shown = shownPosts.get(postId);
  const own = shown.author === authorBox.value.trim();
  shown.edit.hidden = !own;
  shown.remove.hidden = !own;
}

// Show a post's likes: ♥ if the name in the box liked it, ♡ if not.
function showLikes(postId) {
  const names = loadLikes()[postId] || [];
  const youLiked = names.includes(authorBox.value.trim());
  const button = shownPosts.get(postId).like;
  button.textContent = (youLiked ? "♥ " : "♡ ") + names.length;
  button.classList.toggle("liked", youLiked);
  button.setAttribute("aria-pressed", youLiked);
  button.setAttribute("aria-label", "Like this post. " + names.length + " likes.");
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

// The Post button: add a new post, a reply, or an edit, depending on the mode.
function addPost(event) {
  event.preventDefault();
  const author = authorBox.value.trim();
  const text = textBox.value.trim();

  const problem = brokenRule(author, text);
  if (problem !== "") {
    showStatus(problem);
    return;
  }

  const posts = loadPosts();
  if (mode.kind === "edit") {
    const post = posts.find((saved) => saved.id === mode.postId);
    if (post.author !== author) {
      showStatus("You can only edit your own post.");
      return;
    }
    post.text = text;
    post.edited_at = timeNow();
    savePosts(posts);
    showText(post);
  } else {
    // reply_to is null for a new post, or the id of the post being answered.
    const post = { id: posts.length + 1, author: author, text: text, posted_at: timeNow(),
                   reply_to: mode.postId, edited_at: null, deleted_at: null };
    posts.push(post);
    savePosts(posts);
    showPost(post);
  }
  cancelMode();
}

// The Like button: like the post, or take the like back if this name already liked it.
function toggleLike(postId) {
  const name = authorBox.value.trim();
  const problem = brokenNameRule(name);
  if (problem !== "") {
    showStatus(problem);
    return;
  }

  const likes = loadLikes();
  const names = likes[postId] || [];
  // A name is in the list at most once: a second click takes the like back.
  // Only this page's code makes sure of that here. In the backend version
  // the server and the database make sure of it too.
  if (names.includes(name)) {
    likes[postId] = names.filter((liker) => liker !== name);
  } else {
    likes[postId] = names.concat([name]);
  }
  saveLikes(likes);

  showLikes(postId);
  showStatus("");
}

// The Delete button: ask first, because a deleted post cannot come back.
// The words are erased; the post keeps its place, so its replies stay.
function deletePost(postId) {
  const name = authorBox.value.trim();
  const posts = loadPosts();
  const post = posts.find((saved) => saved.id === postId);
  if (post.author !== name) {
    showStatus("You can only delete your own post.");
    return;
  }
  if (!confirm("Delete this post? It cannot be undone.")) {
    return;
  }
  post.text = "";
  post.edited_at = null;
  post.deleted_at = timeNow();
  savePosts(posts);

  const likes = loadLikes();
  delete likes[postId];
  saveLikes(likes);

  if (mode.postId === postId) {
    cancelMode();   // the post being answered or edited is gone
  }
  showText(post);
  showStatus("");
}

// A new name in the box: show the Edit and Delete buttons and likes that belong to that name.
function nameChanged() {
  for (const postId of shownPosts.keys()) {
    showOwnButtons(postId);
    showLikes(postId);
  }
  if (mode.kind === "edit") {
    cancelMode();   // the post being edited may not belong to the new name
  }
}

// When the page opens, show what this window saved before a reload.
// Oldest first, so a post is always on the screen before its replies.
for (const post of loadPosts()) {
  showPost(post);
}

textBox.addEventListener("input", updateCount);
authorBox.addEventListener("input", nameChanged);
cancelButton.addEventListener("click", cancelMode);
postForm.addEventListener("submit", addPost);
