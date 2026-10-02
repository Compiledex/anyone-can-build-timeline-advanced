// Timeline, the advanced version: the start of the page's JavaScript.
//
// The page keeps nothing itself: the server keeps everything. This window keeps a copy of what it
// needs in state.js, and draws the screen from it. It keeps one connection open to the server
// (/events); each time anyone changes anything, the server says so, and the page asks for what is
// new and draws the screen again.

import { get, isOffline, onLoggedOut, send, showOffline, showStatus, toast } from "./api.js";
import { onProfileSaved, onSent, openEditProfile, openLogin, openWrite, updateCount } from "./dialogs.js";
import { exploreLink, postLink, profileLink, readAddress } from "./format.js";
import { fillIcons, icon } from "./icons.js";
import { picturePicker } from "./pictures.js";
import { currentLanguage, currentTheme, nextTheme, setLanguage, setTheme } from "./settings.js";
import { fillWords, t } from "./strings.js";
import { avatar, element, handlers, link } from "./render.js";
import {
  bookmarksScreen, exploreScreen, homeScreen, messagesScreen, notificationsScreen, postScreen, profileHandlers,
  profileScreen, sidebar, sidebarHandlers,
} from "./screens.js";
import {
  addPosts, changed, isBookmarked, likesOf, onChange, setLikes, setMe, setPeople, state, updatePost,
} from "./state.js";

const NOBODY = { name: null, following: [] };

// ---- Drawing the page ----

const screenHolder = document.getElementById("screen");
const pageTitle = document.getElementById("page-title");
const breadcrumb = document.getElementById("breadcrumb");
const tabs = document.getElementById("tabs");
const compose = document.getElementById("compose");
const composeText = document.getElementById("compose-text");
const composeCount = document.getElementById("compose-count");
const composeButton = compose.querySelector("button[type=submit]");
const composePicture = picturePicker(
  compose.querySelector(".compose-tools"), document.getElementById("compose-preview"),
  () => updateComposeCount(), showStatus);

function updateComposeCount() {
  updateCount(composeText, composeCount, composeButton, composePicture.id !== null);
}
const sidebarHolder = document.getElementById("sidebar");
const joinBar = document.getElementById("join-bar");

const SCREENS = {
  home: homeScreen, post: postScreen, profile: profileScreen, explore: exploreScreen, bookmarks: bookmarksScreen,
  notifications: notificationsScreen, messages: messagesScreen,
};
const searchForm = document.getElementById("search-form");
const searchBox = document.getElementById("search-box");
const sideSearch = document.getElementById("side-search");
const sideSearchBox = document.getElementById("side-search-box");
const messageForm = document.getElementById("message-form");
const messageText = document.getElementById("message-text");
const messageSend = document.getElementById("message-send");

function draw() {
  const address = readAddress();
  const shown = SCREENS[address.screen](address);

  // Keep the keyboard where it was: find the button that had it, by its data-focus name.
  const focused = document.activeElement && document.activeElement.dataset
    ? document.activeElement.dataset.focus
    : undefined;

  // As on the real thing: "(3) Timeline" when there are 3 notifications you have not seen.
  const unread = state.unreadNotifications > 0 ? "(" + state.unreadNotifications + ") " : "";
  document.title = unread + (address.screen === "home" ? t("app.name") : shown.title + " · " + t("app.name"));
  pageTitle.textContent = shown.title;
  breadcrumb.replaceChildren();
  shown.breadcrumb.forEach((part, index) => {
    if (index > 0) {
      breadcrumb.append(element("span", "breadcrumb-slash", "／"));
    }
    breadcrumb.append(element("span", "", part));
  });
  tabs.hidden = shown.tabs.length === 0;
  tabs.replaceChildren(...shown.tabs.map((tab) => {
    const made = link(tab.href, "tab", tab.label);
    if (tab.current) {
      made.setAttribute("aria-current", "page");
    }
    return made;
  }));
  compose.hidden = address.screen !== "home" || state.me === null;
  searchForm.hidden = address.screen !== "explore";
  sideSearch.hidden = address.screen === "explore";   // Explore has its own search box
  const inChat = address.screen === "messages" && address.with !== null && state.me !== null && Boolean(state.chat);
  messageForm.hidden = !inChat;
  const messagesBefore = document.querySelectorAll(".message").length;
  screenHolder.replaceChildren(...shown.nodes);
  sidebarHolder.replaceChildren(...sidebar(openLogin));
  drawMenu(address);
  joinBar.hidden = state.me !== null;

  if (focused) {
    const again = document.querySelector('[data-focus="' + CSS.escape(focused) + '"]');
    if (again) {
      again.focus();
    }
  }
  // In a conversation, show the newest message when one arrives, as a chat does.
  if (inChat && document.querySelectorAll(".message").length > messagesBefore) {
    window.scrollTo(0, document.body.scrollHeight);
  }
}

// The menu on the left: which screen is open, and who is logged in.
function drawMenu(address) {
  const ownProfile = address.screen === "profile" && state.me !== null &&
    address.name.toLowerCase() === state.me.toLowerCase();
  for (const item of document.querySelectorAll(".nav-link")) {
    const current = (item.dataset.screen === address.screen && address.screen !== "profile") ||
      (item.dataset.screen === "profile" && ownProfile);
    if (current) {
      item.setAttribute("aria-current", "page");
    } else {
      item.removeAttribute("aria-current");
    }
  }
  const loggedIn = state.me !== null;
  for (const item of document.querySelectorAll("[data-needs-login]")) {
    item.hidden = !loggedIn;
  }
  const badge = document.getElementById("nav-badge");
  badge.hidden = state.unreadNotifications === 0;
  badge.textContent = state.unreadNotifications > 99 ? "99+" : String(state.unreadNotifications);
  badge.parentElement.parentElement.setAttribute("aria-label", state.unreadNotifications > 0
    ? t("nav.notificationsNew", { count: state.unreadNotifications }) : t("nav.notifications"));
  const messagesBadge = document.getElementById("nav-messages-badge");
  messagesBadge.hidden = state.unreadMessages === 0;
  messagesBadge.textContent = state.unreadMessages > 99 ? "99+" : String(state.unreadMessages);
  messagesBadge.parentElement.parentElement.setAttribute("aria-label", state.unreadMessages > 0
    ? t("nav.messagesNew", { count: state.unreadMessages }) : t("nav.messages"));
  document.getElementById("nav-profile").hidden = !loggedIn;
  document.getElementById("nav-post").hidden = !loggedIn;
  document.getElementById("nav-me").hidden = !loggedIn;
  if (loggedIn) {
    document.getElementById("nav-profile").href = profileLink(state.me);
    document.getElementById("nav-me-link").href = profileLink(state.me);
    document.getElementById("nav-me-name").textContent = state.me;
    document.getElementById("nav-me-avatar").replaceChildren(avatar(state.me, "small", false, state.avatar));
    document.getElementById("compose-avatar").replaceChildren(avatar(state.me, "normal", false, state.avatar));
  }
}

onChange(draw);

// ---- Asking the server ----

async function checkMe() {
  setMe(await get("/me"));
}

async function checkPeople() {
  setPeople(await get("/people"));
}

async function checkPosts() {
  addPosts(await get("/posts?after=" + state.lastId));
}

async function checkLikes() {
  setLikes(await get("/likes"));
}

async function checkBookmarks() {
  state.bookmarks = state.me === null ? [] : (await get("/bookmarks")).post_ids;
}

// On the Notifications page: fetch them, then mark them read. They stay marked "new" on the
// screen until the next visit, so you can see which ones you had not seen.
async function checkNotifications() {
  if (readAddress().screen !== "notifications" || state.me === null) {
    return;
  }
  state.notifications = await get("/notifications");
  if (state.notifications.some((told) => !told.read)) {
    const { answer } = await send("POST", "/notifications/read");
    if (answer) {
      setMe(answer);
    }
  }
}

// On the Messages page: the list of conversations, or one conversation (marked read once seen).
async function checkMessages() {
  const address = readAddress();
  if (address.screen !== "messages" || state.me === null) {
    return;
  }
  if (address.with === null) {
    state.conversations = await get("/messages");
    return;
  }
  try {
    state.chat = await get("/messages?with=" + encodeURIComponent(address.with));
  } catch (error) {
    state.chat = false;   // there is no one with that name
    return;
  }
  if (state.chat.messages.some((message) => !message.from_me && !message.read)) {
    const { answer } = await send("POST", "/messages/read", { with: state.chat.with });
    if (answer) {
      setMe(answer);
    }
  }
}

async function checkChanges() {
  for (const post of await get("/changes")) {
    updatePost(post);
  }
}

async function checkProfile() {
  const address = readAddress();
  if (address.screen !== "profile") {
    return;
  }
  try {
    state.profile = await get("/users?name=" + encodeURIComponent(address.name));
  } catch (error) {
    state.profile = false;   // there is no one with that name
  }
}

async function checkSidebar() {
  state.sidebar = await get("/sidebar");
}

async function checkSearch() {
  const address = readAddress();
  if (address.screen !== "explore" || address.query === "") {
    return;
  }
  try {
    state.search = { query: address.query, ...(await get("/search?q=" + encodeURIComponent(address.query))) };
  } catch (error) {
    state.search = { query: address.query, error: error.message };
  }
}

// ---- Live updates ----
// The page keeps one connection open to /events: this is Server-Sent Events, and the browser's
// EventSource does the work. The server sends "changed" each time anyone changes anything, and
// the page catches up. If the connection drops, EventSource connects again by itself, and the
// server's first message ("hello") makes the page catch up on anything it missed.

let catchingUp = false;
let catchUpAgain = false;

// Ask for everything new: posts first, so that every post is here before its likes and changes.
// If a message comes while we are still asking, go once more.
async function catchUp() {
  if (catchingUp) {
    catchUpAgain = true;
    return;
  }
  catchingUp = true;
  do {
    catchUpAgain = false;
    try {
      await checkMe();
      await checkPeople();
      await checkPosts();
      await checkLikes();
      await checkBookmarks();
      await checkChanges();
      await checkSidebar();
      await checkProfile();
      await checkSearch();
      await checkNotifications();
      await checkMessages();
      if (isOffline()) {
        showStatus("");
      }
    } catch (error) {
      showOffline();
    }
    changed();
  } while (catchUpAgain);
  catchingUp = false;
}

function listen() {
  const events = new EventSource("/events");
  events.addEventListener("message", catchUp);
  events.addEventListener("error", showOffline);
}

// ---- What the buttons do ----

handlers.reply = (postId) => openWrite("reply", postId);
handlers.quote = (postId) => openWrite("quote", postId);

handlers.repost = async (postId, undo) => {
  if (state.me === null) {
    openLogin("login");
    return;
  }
  const { error } = await send(undo ? "DELETE" : "POST", "/reposts", { post_id: postId });
  if (error) {
    showStatus(error);
    return;
  }
  toast(t(undo ? "toast.repostUndone" : "toast.reposted"));
  await catchUp();
};
handlers.edit = (postId) => openWrite("edit", postId);

handlers.like = async (postId) => {
  if (state.me === null) {
    openLogin("login");
    return;
  }
  const { answer, error } = await send(likesOf(postId).you_liked ? "DELETE" : "POST", "/likes",
                                       { post_id: postId });
  if (error) {
    showStatus(error);
    return;
  }
  setLikes(answer);
  changed();
};

handlers.bookmark = async (postId) => {
  if (state.me === null) {
    openLogin("login");
    return;
  }
  const saved = isBookmarked(postId);
  const { answer, error } = await send(saved ? "DELETE" : "POST", "/bookmarks", { post_id: postId });
  if (error) {
    showStatus(error);
    return;
  }
  state.bookmarks = answer.post_ids;
  changed();
  toast(t(saved ? "toast.bookmarkRemoved" : "toast.bookmarkAdded"));
};

handlers.remove = async (postId) => {
  if (!confirm(t("confirm.delete"))) {
    return;
  }
  const { answer, error } = await send("DELETE", "/posts", { post_id: postId });
  if (error) {
    showStatus(error);
    return;
  }
  updatePost(answer);
  changed();
  toast(t("toast.deleted"));
};

profileHandlers.follow = async () => {
  const person = state.profile;
  const { answer, error } = await send(person.you_follow ? "DELETE" : "POST", "/follows", { name: person.name });
  if (error) {
    showStatus(error);
    return;
  }
  setMe(answer);
  await checkProfile();
  changed();
};

profileHandlers.edit = openEditProfile;

sidebarHandlers.follow = async (name) => {
  const { answer, error } = await send("POST", "/follows", { name: name });
  if (error) {
    showStatus(error);
    return;
  }
  setMe(answer);
  await checkSidebar().catch(() => {});
  changed();
  toast(t("toast.followNow", { name: name }));
};

onProfileSaved(async () => {
  await checkPeople().catch(() => {});
  await checkProfile();
  changed();
  toast(t("toast.profileSaved"));
});

// After a post, a reply or an edit was sent: catch up, and say so.
onSent((kind, post) => {
  if (kind === "edit") {
    updatePost(post);
    changed();
  }
  catchUp();
  toast(t("toast.sent." + kind));
  if (kind === "reply" && readAddress().screen !== "post") {
    location.hash = postLink(post.reply_to);
  }
});

// The post box on Home.
composeText.addEventListener("input", updateComposeCount);
compose.addEventListener("submit", async (event) => {
  event.preventDefault();
  composeButton.disabled = true;
  const { error } = await send("POST", "/posts", { text: composeText.value, picture_id: composePicture.id });
  if (error) {
    showStatus(error);
    updateComposeCount();
    return;
  }
  composeText.value = "";
  composePicture.clear();
  updateComposeCount();
  showStatus("");
  catchUp();
});

document.getElementById("nav-post").addEventListener("click", () => openWrite("post"));

document.getElementById("log-out").addEventListener("click", async () => {
  await send("POST", "/logout");
  setMe(NOBODY);
  state.bookmarks = [];
  state.conversations = [];
  state.chat = null;
  await checkLikes().catch(() => {});
  changed();
  toast(t("toast.loggedOut"));
});

for (const button of document.querySelectorAll("[data-open-login]")) {
  button.addEventListener("click", () => openLogin(button.dataset.openLogin));
}

onLoggedOut(() => {
  setMe(NOBODY);
  changed();
});

// A "⋯" menu closes when you click anywhere else.
document.addEventListener("click", (event) => {
  for (const menu of document.querySelectorAll("details.post-menu[open]")) {
    if (!menu.contains(event.target)) {
      menu.open = false;
    }
  }
});

// A search: its words go into the address, so Back works and the search can be shared.
searchForm.addEventListener("submit", (event) => {
  event.preventDefault();
  location.hash = exploreLink(searchBox.value.trim());
});
// Sending a message. Enter sends; Shift+Enter makes a new line.
messageText.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
    event.preventDefault();
    messageForm.requestSubmit();
  }
});
messageForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  if (messageText.value.trim() === "" || !state.chat) {
    return;
  }
  messageSend.disabled = true;
  const { error } = await send("POST", "/messages", { to: state.chat.with, text: messageText.value });
  messageSend.disabled = false;
  if (error) {
    showStatus(error);
    return;
  }
  messageText.value = "";
  messageText.focus();
  await catchUp();
});

sideSearch.addEventListener("submit", (event) => {
  event.preventDefault();
  location.hash = exploreLink(sideSearchBox.value.trim());
  sideSearchBox.value = "";
});

// A new address: draw its screen, and ask for the profile or the search if it is one.
async function addressChanged() {
  state.profile = null;
  state.chat = null;
  const address = readAddress();
  if (address.screen === "explore") {
    searchBox.value = address.query;
  }
  draw();
  window.scrollTo(0, 0);
  await checkProfile().catch(() => {});
  await checkSearch();
  await checkNotifications().catch(() => {});
  await checkMessages().catch(() => {});
  changed();
  if (readAddress().screen === "messages" && readAddress().with) {
    window.scrollTo(0, document.body.scrollHeight);
    messageText.focus();
  }
}

window.addEventListener("hashchange", addressChanged);

// The colours switch at the top: System → Light → Dark. It shows the one in use now.
const themeButton = document.getElementById("theme-button");
const THEME_ICON = { system: "system", light: "sun", dark: "moon" };

function drawThemeButton() {
  const theme = currentTheme();
  const words = t("theme." + theme);
  themeButton.replaceChildren(icon(THEME_ICON[theme]), document.createTextNode(words));
  themeButton.setAttribute("aria-label", t("theme.label", { mode: words }));
  themeButton.title = t("theme.title", { mode: words });
}

themeButton.addEventListener("click", () => {
  setTheme(nextTheme());
  drawThemeButton();
});

// The language switch: it shows the other language, in that language ("日本語" or "English").
const languageButton = document.getElementById("language-button");

function drawLanguageButton() {
  languageButton.replaceChildren(icon("globe"), document.createTextNode(t("language.other")));
  languageButton.lang = currentLanguage() === "ja" ? "en" : "ja";   // so a screen reader says it right
  languageButton.setAttribute("aria-label", t("language.label"));
  languageButton.title = t("language.label");
}

languageButton.addEventListener("click", () => {
  setLanguage(currentLanguage() === "ja" ? "en" : "ja");
  fillWords();            // the fixed words in index.html
  drawLanguageButton();
  drawThemeButton();
  if (isOffline()) {
    showOffline();        // the same message, in the new language
  }
  changed();              // everything else is drawn again, in the new language
});

// Times like "5m" grow older: draw again every minute.
setInterval(changed, 60 * 1000);

fillIcons();
fillWords();
drawLanguageButton();
drawThemeButton();
updateComposeCount();
addressChanged();
listen();
