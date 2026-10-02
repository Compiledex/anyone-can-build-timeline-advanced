// Timeline, the advanced version.
//
// This page keeps nothing itself. It sends each sign-up, log-in, post, reply, edit, delete
// and like to the server (server.py), and every second it asks the server three things:
// "any new posts?", "how many likes?" and "which posts were edited or deleted?"
//
// The server knows who you are from a cookie it set when you logged in. The page never sees
// that cookie: it is HttpOnly, so JavaScript cannot read it, and the browser sends it by itself.

const MAX_TEXT = 280;
const CANNOT_REACH = "Cannot reach the server. Trying again every second.";

const accountBar = document.getElementById("account-bar");
const meName = document.getElementById("me-name");
const logOutButton = document.getElementById("log-out");
const loginForm = document.getElementById("login-form");
const loginName = document.getElementById("login-name");
const loginPassword = document.getElementById("login-password");
const signUpButton = document.getElementById("sign-up");
const postForm = document.getElementById("post-form");
const textBox = document.getElementById("text");
const countLine = document.getElementById("count");
const statusLine = document.getElementById("status");
const timeline = document.getElementById("timeline");
const modeLine = document.getElementById("mode-line");
const modeText = document.getElementById("mode-text");
const cancelButton = document.getElementById("cancel-mode");
const submitButton = document.getElementById("submit-button");
const profileSection = document.getElementById("profile");
const profileName = document.getElementById("profile-name");
const profileFacts = document.getElementById("profile-facts");
const emptyLine = document.getElementById("empty");

// The logged-in person's name, or null when nobody is logged in.
let me = null;

// The id of the newest post this window has shown. 0 means "none yet".
let lastId = 0;

// Each post on the screen, found by its id: its author, and the parts that can change.
const shownPosts = new Map();

// What the box is for right now: a new post, a reply to a post, or an edit of a post.
let mode = { kind: "post", postId: null };

// ---- Showing things ----

// "2026-10-02 15:42" becomes "15:42" today, "Yesterday 15:42", or "30 Sep 15:42".
function shortTime(stamp) {
  if (!stamp) {
    return "";
  }
  const [day, clock] = stamp.split(" ");
  const date = new Date(day + "T00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const daysAgo = Math.round((today - date) / (24 * 60 * 60 * 1000));
  if (daysAgo === 0) {
    return clock;
  }
  if (daysAgo === 1) {
    return "Yesterday " + clock;
  }
  return date.toLocaleDateString("en-GB", { day: "numeric", month: "short" }) + " " + clock;
}

// "2026-10-02 15:42" becomes "2 October 2026".
function longDate(stamp) {
  return new Date(stamp.split(" ")[0] + "T00:00")
    .toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });
}

// "1 post", "2 posts".
function plural(count, word) {
  return count + " " + word + (count === 1 ? "" : "s");
}

// ---- Screens: the timeline, or one person's profile ----
// The address says which: "#/" is the timeline, "#/@Ben" is Ben's profile.
// Because the screen is in the address, the browser's Back button works.

function profileInAddress() {
  let address = location.hash;
  try {
    address = decodeURIComponent(address);
  } catch (error) {
    // A broken address, like "#/@%": use it as it is.
  }
  return address.startsWith("#/@") ? address.slice(3) : null;
}

function profileLink(name) {
  return "#/@" + encodeURIComponent(name);
}

// Show the screen the address asks for.
function showScreen() {
  const name = profileInAddress();
  profileSection.hidden = name === null;
  document.title = name === null ? "Timeline" : name + " · Timeline";
  if (name !== null) {
    profileName.textContent = name;
    profileFacts.textContent = "";
    checkProfile();
  }
  filterPosts();
}

// Show only the threads that belong on this screen. A thread is a post with all its replies.
// On a profile, a thread belongs if the person wrote the post or any reply in it.
function filterPosts() {
  const name = profileInAddress();
  let shownAny = false;
  for (const item of timeline.children) {
    const belongs = name === null || threadHasAuthor(item, name);
    item.hidden = !belongs;
    shownAny = shownAny || belongs;
  }
  emptyLine.hidden = shownAny;
}

function threadHasAuthor(item, name) {
  const wanted = name.toLowerCase();   // names are the same whatever their capitals
  const posts = [item, ...item.querySelectorAll(".post")];
  return posts.some((post) => post.dataset.author.toLowerCase() === wanted);
}

// Put one post on the screen: a new post at the top, a reply under its post.
function showPost(post) {
  // Skip a post this window already shows.
  if (post.id <= lastId) {
    return;
  }
  lastId = post.id;

  const item = document.createElement("li");
  item.className = "post";
  item.dataset.author = post.author;

  const author = document.createElement("a");
  author.className = "post-author";
  author.href = profileLink(post.author);
  author.textContent = post.author;

  const time = document.createElement("span");
  time.className = "post-time";
  time.textContent = shortTime(post.posted_at);
  time.title = post.posted_at;

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

  shownPosts.set(post.id, { author: post.author, item, text, edited, buttons, like, reply, edit, remove, replies });
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
  shown.edited.textContent = post.edited_at ? "edited " + shortTime(post.edited_at) : "";
}

// Reply shows only when someone is logged in. Edit and Delete show only on your own posts.
// The server checks this again: it knows who you are from your login.
function showOwnButtons(postId) {
  const shown = shownPosts.get(postId);
  const own = me !== null && shown.author === me;
  shown.reply.hidden = me === null;
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

// Show who is logged in: the bar at the top and the post box, or the log-in box.
function showMe(name) {
  me = name;
  accountBar.hidden = me === null;
  meName.textContent = me || "";
  meName.href = me ? profileLink(me) : "#/";
  loginForm.hidden = me !== null;
  postForm.hidden = me === null;
  for (const postId of shownPosts.keys()) {
    showOwnButtons(postId);
  }
  if (me === null && mode.kind !== "post") {
    cancelMode();
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

// ---- The post box: a new post, a reply, or an edit ----

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

// ---- Talking to the server ----

// Send something to the server. Returns the server's answer,
// or null after showing why it did not work.
async function send(method, path, data) {
  try {
    const response = await fetch(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
    const answer = await response.json();
    if (response.status === 401) {
      showMe(null);   // the login ended, for example after 30 days
    }
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

// Ask the server who is logged in in this browser.
async function checkMe() {
  try {
    const response = await fetch("/me");
    showMe((await response.json()).name);
  } catch (error) {
    showStatus(CANNOT_REACH);
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
    if (posts.length > 0) {
      filterPosts();
    }
    if (statusLine.textContent === CANNOT_REACH) {
      showStatus("");
    }
  } catch (error) {
    showStatus(CANNOT_REACH);
  }
}

// Ask the server how many likes each post has, and which ones you liked.
async function checkLikes() {
  try {
    const response = await fetch("/likes");
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

// On a profile screen, ask the server about that person.
async function checkProfile() {
  const name = profileInAddress();
  if (name === null) {
    return;
  }
  try {
    const response = await fetch("/users?name=" + encodeURIComponent(name));
    const person = await response.json();
    if (profileInAddress() !== name) {
      return;   // the screen changed while we waited
    }
    if (!response.ok) {
      profileFacts.textContent = person.error;   // "There is no one called …"
      return;
    }
    profileName.textContent = person.name;
    profileFacts.textContent = "Joined " + longDate(person.joined_at) + " · " + plural(person.posts, "post");
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
  await checkProfile();
  setTimeout(keepChecking, 1000);
}

// ---- What the buttons do ----

// Log in, or sign up: both send the name and password, and both log this browser in.
async function logInOrSignUp(path) {
  const name = loginName.value;
  const password = loginPassword.value;

  // A quick check on the page. The server checks the same rules again.
  if (name.trim() === "") {
    showStatus("The name must not be empty.");
    return;
  }
  if (path === "/signup" && password.length < 8) {
    showStatus("The password must be at least 8 characters.");
    return;
  }

  const answer = await send("POST", path, { name: name, password: password });
  if (!answer) {
    return;
  }
  loginPassword.value = "";
  showMe(answer.name);
  await checkLikes();
}

async function logOut() {
  await send("POST", "/logout");
  showMe(null);
  await checkLikes();
}

// The Post button: send a new post, a reply, or an edit, depending on the mode.
async function sendPost(event) {
  event.preventDefault();
  const text = textBox.value;

  // A quick check on the page, so the person does not wait for an answer.
  // The server checks the same rules again. Never trust only the screen:
  // anyone can send a request without using this page at all.
  if (text.trim() === "") {
    showStatus("The post must not be empty.");
    return;
  }

  if (mode.kind === "edit") {
    const post = await send("PUT", "/posts", { post_id: mode.postId, text: text });
    if (!post) {
      return;
    }
    showText(post);
  } else {
    // reply_to is null for a new post, or the id of the post being answered.
    const post = await send("POST", "/posts", { text: text, reply_to: mode.postId });
    if (!post) {
      return;
    }
  }
  // Saved. Ask for new posts now, instead of waiting for the next second.
  cancelMode();
  await checkForNewPosts();
}

// The Like button: like the post, or take the like back if you already liked it.
async function toggleLike(postId, button) {
  if (me === null) {
    showStatus("Log in to like posts.");
    return;
  }
  button.disabled = true;   // so a double-click sends only one request
  const method = button.classList.contains("liked") ? "DELETE" : "POST";
  const counts = await send(method, "/likes", { post_id: postId });
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
  const post = await send("DELETE", "/posts", { post_id: postId });
  if (post) {
    showText(post);
  }
}

loginForm.addEventListener("submit", (event) => {
  event.preventDefault();
  logInOrSignUp("/login");
});
signUpButton.addEventListener("click", () => logInOrSignUp("/signup"));
logOutButton.addEventListener("click", logOut);
textBox.addEventListener("input", updateCount);
cancelButton.addEventListener("click", cancelMode);
postForm.addEventListener("submit", sendPost);
window.addEventListener("hashchange", () => {
  showScreen();
  window.scrollTo(0, 0);
});
showScreen();
checkMe().then(keepChecking);
