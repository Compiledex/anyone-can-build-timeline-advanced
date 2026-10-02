// Talking to the server. The browser sends the login cookie by itself with every request;
// this page cannot read it (it is HttpOnly), and does not need to.
// The server's messages are in English; fromServer shows them in the page's language.

import { fromServer, t } from "./strings.js";

let whenLoggedOut = () => {};

// What to do when the server says nobody is logged in (401), for example after 30 days.
export function onLoggedOut(listener) {
  whenLoggedOut = listener;
}

// Send a change to the server. Returns { answer } when it worked, or { error } with the
// reason: the rule the server says was broken, or that it cannot be reached.
export async function send(method, path, data) {
  try {
    const response = await fetch(path, {
      method: method,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {}),
    });
    const answer = await response.json();
    if (response.status === 401) {
      whenLoggedOut();
    }
    if (!response.ok) {
      return { error: fromServer(answer.error) };
    }
    return { answer: answer };
  } catch (error) {
    return { error: t("status.cannotReach") };
  }
}

// Send a picture. Its bytes are the whole request, with its type. Returns { answer } or { error }.
export async function uploadPicture(file) {
  try {
    const response = await fetch("/uploads", {
      method: "POST",
      headers: { "Content-Type": file.type },
      body: file,
    });
    const answer = await response.json();
    if (response.status === 401) {
      whenLoggedOut();
    }
    return response.ok ? { answer: answer } : { error: fromServer(answer.error) };
  } catch (error) {
    return { error: t("status.cannotReach") };
  }
}

// Ask the server for something. Throws when it cannot answer.
export async function get(path) {
  const response = await fetch(path);
  const answer = await response.json();
  if (!response.ok) {
    throw new Error(fromServer(answer.error));
  }
  return answer;
}

// The line under the header, for problems.
export function showStatus(words) {
  const line = document.getElementById("status");
  delete line.dataset.offline;
  line.textContent = words;
  line.hidden = !words;
}

// "Cannot reach the server": marked, so that it can be taken away when the server is back.
export function showOffline() {
  showStatus(t("status.cannotReach"));
  document.getElementById("status").dataset.offline = "yes";
}

export function isOffline() {
  return document.getElementById("status").dataset.offline === "yes";
}

// A short message at the bottom that goes away by itself, for things that worked.
export function toast(words) {
  const note = document.createElement("p");
  note.className = "toast";
  note.setAttribute("role", "status");
  note.textContent = words;
  document.body.append(note);
  setTimeout(() => note.remove(), 3000);
}
