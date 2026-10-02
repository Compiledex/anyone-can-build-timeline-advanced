// The windows that open over the page: logging in, and writing (a post, a reply or an edit).
// They use the browser's own <dialog>, which keeps the keyboard inside the window
// and closes with the Escape key.

import { send } from "./api.js";
import { postCard } from "./render.js";
import { changed, setMe, state } from "./state.js";

export const MAX_TEXT = 280;

// ---- Logging in, or signing up ----

const loginDialog = document.getElementById("login-dialog");
const loginForm = document.getElementById("login-form");
const loginTitle = document.getElementById("login-title");
const loginName = document.getElementById("login-name");
const loginPassword = document.getElementById("login-password");
const loginError = document.getElementById("login-error");
const loginSubmit = document.getElementById("login-submit");
const loginSwitch = document.getElementById("login-switch");

let loginMode = "login";

export function openLogin(mode) {
  loginMode = mode;
  const signingUp = mode === "signup";
  loginTitle.textContent = signingUp ? "Join Timeline" : "Log in to Timeline";
  loginSubmit.textContent = signingUp ? "Sign up" : "Log in";
  loginPassword.autocomplete = signingUp ? "new-password" : "current-password";
  loginError.textContent = "";
  loginSwitch.replaceChildren(
    document.createTextNode(signingUp ? "Already have an account? " : "Don't have an account? "),
    switchButton(signingUp ? "Log in" : "Sign up", signingUp ? "login" : "signup"));
  if (!loginDialog.open) {
    loginDialog.showModal();
  }
  loginName.focus();
}

function switchButton(words, mode) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "text-button";
  button.textContent = words;
  button.addEventListener("click", () => openLogin(mode));
  return button;
}

loginForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  // A quick check on the page. The server checks the same rules again.
  if (loginName.value.trim() === "") {
    loginError.textContent = "The name must not be empty.";
    return;
  }
  if (loginMode === "signup" && loginPassword.value.length < 8) {
    loginError.textContent = "The password must be at least 8 characters.";
    return;
  }
  loginSubmit.disabled = true;
  const { answer, error } = await send("POST", loginMode === "signup" ? "/signup" : "/login",
                                       { name: loginName.value, password: loginPassword.value });
  loginSubmit.disabled = false;
  if (error) {
    loginError.textContent = error;
    return;
  }
  loginPassword.value = "";
  loginDialog.close();
  setMe(answer);
  changed();
});

// ---- Writing: a new post, a reply, or an edit ----

const writeDialog = document.getElementById("compose-dialog");
const writeForm = document.getElementById("compose-dialog-form");
const writeTitle = document.getElementById("compose-dialog-title");
const writeOriginal = document.getElementById("compose-dialog-original");
const writeText = document.getElementById("compose-dialog-text");
const writeError = document.getElementById("compose-dialog-error");
const writeCount = document.getElementById("compose-dialog-count");
const writeSubmit = document.getElementById("compose-dialog-submit");

let writing = { kind: "post", postId: null };
let whenSent = () => {};

// What to do after something was sent (main.js asks the server for what is new).
export function onSent(listener) {
  whenSent = listener;
}

// kind is "post", "reply" or "edit"; postId is the post replied to or edited.
export function openWrite(kind, postId = null) {
  if (state.me === null) {
    openLogin("login");
    return;
  }
  writing = { kind: kind, postId: postId };
  const original = state.posts.get(postId);
  writeTitle.textContent = { post: "New post", reply: "Reply", edit: "Edit your post" }[kind];
  writeSubmit.textContent = { post: "Post", reply: "Reply", edit: "Save" }[kind];
  writeText.placeholder = kind === "reply" ? "Post your reply" : "What is happening?";
  writeOriginal.replaceChildren();
  if (kind === "reply" && original) {
    writeOriginal.append(postCard(original, { preview: true }));
  }
  writeText.value = kind === "edit" && original ? original.text : "";
  writeError.textContent = "";
  updateCount(writeText, writeCount, writeSubmit);
  writeDialog.showModal();
  writeText.focus();
}

writeText.addEventListener("input", () => updateCount(writeText, writeCount, writeSubmit));

writeForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const text = writeText.value;
  if (text.trim() === "") {
    writeError.textContent = "The post must not be empty.";
    return;
  }
  writeSubmit.disabled = true;
  const { answer, error } = writing.kind === "edit"
    ? await send("PUT", "/posts", { post_id: writing.postId, text: text })
    : await send("POST", "/posts", { text: text, reply_to: writing.kind === "reply" ? writing.postId : null });
  writeSubmit.disabled = false;
  if (error) {
    writeError.textContent = error;
    return;
  }
  writeDialog.close();
  whenSent(writing.kind, answer);
});

// The count next to a Post button: shown from 260 characters on, red over the limit.
// The button only works when there is something to send, and not too much.
export function updateCount(box, countLine, button) {
  const length = box.value.length;
  countLine.textContent = length >= MAX_TEXT - 20 ? String(MAX_TEXT - length) : "";
  countLine.classList.toggle("too-long", length > MAX_TEXT);
  button.disabled = box.value.trim() === "" || length > MAX_TEXT;
}

// Every window closes with its × button, and by clicking outside it.
for (const dialog of [loginDialog, writeDialog]) {
  dialog.querySelector("[data-close]").addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (event) => {
    if (event.target === dialog) {
      dialog.close();   // the click was on the dark area around the window
    }
  });
}
