// Talking to the server. The browser sends the login cookie by itself with every request;
// this page cannot read it (it is HttpOnly), and does not need to.

export const CANNOT_REACH = "Cannot reach the server. Trying again every second.";

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
      return { error: answer.error };
    }
    return { answer: answer };
  } catch (error) {
    return { error: CANNOT_REACH };
  }
}

// Ask the server for something. Throws when it cannot answer.
export async function get(path) {
  const response = await fetch(path);
  const answer = await response.json();
  if (!response.ok) {
    throw new Error(answer.error);
  }
  return answer;
}

// The line under the header, for problems.
export function showStatus(words) {
  const line = document.getElementById("status");
  line.textContent = words;
  line.hidden = !words;
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
