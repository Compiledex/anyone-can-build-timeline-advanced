// Drawing things: an avatar, a post card, a thread of replies.
// Everything a user typed is put on the page with textContent, never innerHTML,
// so a post is always shown as words and can never run code on the page.

import { icon } from "./icons.js";
import { t } from "./strings.js";
import { avatarColour, exploreLink, fullTime, initials, postLink, profileLink, shortTime } from "./format.js";
import {
  avatarOf, isBookmarked, isMe, isShown, likesOf, replyCount, repliesTo, repostCount, state, youReposted,
} from "./state.js";

// What the buttons on a post do. main.js fills these in.
export const handlers = {
  reply: (postId) => {},
  like: (postId) => {},
  repost: (postId, undo) => {},
  bookmark: (postId) => {},
  quote: (postId) => {},
  edit: (postId) => {},
  remove: (postId) => {},
};

// A new element with a class, and maybe some text.
export function element(tag, className, text) {
  const made = document.createElement(tag);
  if (className) {
    made.className = className;
  }
  if (text !== undefined) {
    made.textContent = text;
  }
  return made;
}

export function link(href, className, text) {
  const made = element("a", className, text);
  made.href = href;
  return made;
}

// A round picture for a person: their picture, or the first letter of their name on their own colour.
// picture: the address of a picture to show instead (in the Edit profile window).
export function avatar(name, size = "normal", asLink = true, picture = undefined) {
  const made = asLink ? link(profileLink(name), "avatar avatar-" + size) : element("span", "avatar avatar-" + size);
  made.style.setProperty("--avatar-colour", avatarColour(name));
  const address = picture !== undefined ? picture : avatarOf(name);
  if (address) {
    const image = element("img");
    image.src = address;
    image.alt = "";
    made.append(image);
  } else {
    made.append(element("span", "avatar-letter", initials(name)));
  }
  if (asLink) {
    made.setAttribute("aria-label", name);
    made.tabIndex = -1;   // the name next to it is the same link, for the keyboard
  } else {
    made.setAttribute("aria-hidden", "true");
  }
  return made;
}

// A post's words, with #tags, @names and web addresses made into links.
// Each piece is added as text or as a link with text, never as HTML.
// A # or @ starts a link only when no letter comes right before it, so "a@b.c" stays plain.
const LINKABLE = /(https?:\/\/[^\s<>"]*[^\s<>".,!?)])|(?<![\p{L}\p{N}_])([#@])([\p{L}\p{N}_]{1,50})/gu;

export function postText(text) {
  const words = document.createDocumentFragment();
  let from = 0;
  for (const found of text.matchAll(LINKABLE)) {
    words.append(document.createTextNode(text.slice(from, found.index)));
    if (found[1]) {
      // Only http and https addresses come here, so a link can never run code.
      const outside = link(found[1], "post-link", found[1]);
      outside.target = "_blank";
      outside.rel = "noopener noreferrer nofollow";
      words.append(outside);
    } else if (found[2] === "#") {
      words.append(link(exploreLink("#" + found[3]), "post-link", "#" + found[3]));
    } else {
      words.append(link(profileLink(found[3]), "post-link", "@" + found[3]));
    }
    from = found.index + found[0].length;
  }
  words.append(document.createTextNode(text.slice(from)));
  return words;
}

// One post. options.preview: no buttons (inside a window). options.big: the post on its own page.
// options.replyingTo: say which post this one answers.
// A repost is drawn as the post it shares, with "Ben reposted" above it.
export function postCard(post, options = {}) {
  if (post.repost_of !== null) {
    const original = state.posts.get(post.repost_of);
    return postCard(original, { ...options, repost: post });
  }
  const card = element("article", "post-card" + (options.big ? " post-card-big" : ""));
  card.dataset.id = post.id;
  // The same post can be on the screen twice (itself, and a repost of it): keep their buttons apart.
  const focusPrefix = options.repost ? "repost" + options.repost.id + "-" : "";

  if (post.deleted_at) {
    card.classList.add("deleted");
    card.append(element("p", "post-deleted-text", t("post.deleted")));
    opensOnClick(card, post, options);   // its replies are on its own page
    return card;
  }

  const main = element("div", "post-main");
  if (options.repost) {
    const line = element("p", "post-reposted");
    line.append(icon("repost"), document.createTextNode(
      isMe(options.repost.author) ? t("post.youReposted") : t("post.reposted", { name: options.repost.author })));
    main.append(line);
  }
  const head = element("div", "post-head");
  head.append(link(profileLink(post.author), "post-author", post.author));
  if (!options.big) {
    const time = link(postLink(post.id), "post-time", shortTime(post.posted_at));
    time.title = fullTime(post.posted_at);
    head.append(element("span", "post-dot", "·"), time);
  }
  if (post.edited_at) {
    head.append(element("span", "post-edited", t("post.edited")));
  }
  if (!options.preview && isMe(post.author)) {
    head.append(ownMenu(post));
  }
  main.append(head);

  if (options.replyingTo && post.reply_to !== null) {
    const parent = state.posts.get(post.reply_to);
    if (parent && !parent.deleted_at) {
      const line = element("p", "post-replying", t("post.replyingTo"));
      line.append(link(profileLink(parent.author), "", "@" + parent.author));
      main.append(line);
    }
  }

  if (post.text) {
    const text = element("p", "post-text");
    text.append(postText(post.text));
    main.append(text);
  }
  if (post.picture) {
    main.append(postPicture(post));
  }
  if (post.quote_of !== null) {
    main.append(quoteBox(state.posts.get(post.quote_of)));
  }

  if (options.big) {
    main.append(element("p", "post-full-time", fullTime(post.posted_at)));
  }
  if (!options.preview) {
    main.append(actionBar(post, focusPrefix));
  }
  card.append(avatar(post.author), main);
  opensOnClick(card, post, options);
  return card;
}

// Clicking a card (not a link or a button in it) opens the post on its own page.
function opensOnClick(card, post, options) {
  if (options.preview || options.big) {
    return;
  }
  card.classList.add("clickable");
  card.addEventListener("click", (event) => {
    const onSomething = event.target.closest("a, button, details, input, textarea, label");
    const selecting = window.getSelection().toString() !== "";
    if (!onSomething && !selecting) {
      location.hash = postLink(post.id);
    }
  });
}

function postPicture(post) {
  const picture = element("img", "post-picture");
  picture.src = post.picture;
  picture.alt = t("post.pictureAlt", { name: post.author });
  picture.loading = "lazy";
  return picture;
}

// The post a quote shows: small, in a box, opening the post when clicked.
function quoteBox(quoted) {
  if (!quoted || quoted.deleted_at) {
    return element("div", "quote-box quote-box-gone", t("post.deleted"));
  }
  const box = link(postLink(quoted.id), "quote-box");
  const head = element("span", "quote-head");
  head.append(avatar(quoted.author, "tiny", false), element("span", "quote-author", quoted.author),
              element("span", "post-dot", "·"), element("span", "post-time", shortTime(quoted.posted_at)));
  box.append(head);
  if (quoted.text) {
    box.append(element("span", "quote-text", quoted.text));   // plain words: the whole box is one link
  }
  if (quoted.picture) {
    box.append(postPicture(quoted));
  }
  return box;
}

// The row of buttons under a post: reply, repost and like, each with its count, and bookmark.
function actionBar(post, focusPrefix) {
  const bar = element("div", "post-actions");
  const replies = replyCount(post.id);
  bar.append(actionButton(focusPrefix, post.id, "reply", false, replies, t("action.reply"),
                          () => handlers.reply(post.id)));
  bar.append(repostMenu(post, focusPrefix));
  const likes = likesOf(post.id);
  bar.append(actionButton(focusPrefix, post.id, "heart", likes.you_liked, likes.likes,
                          likes.you_liked ? t("action.unlike") : t("action.like"), () => handlers.like(post.id)));
  const saved = isBookmarked(post.id);
  bar.append(actionButton(focusPrefix, post.id, "bookmark", saved, 0,
                          saved ? t("action.unbookmark") : t("action.bookmark"), () => handlers.bookmark(post.id)));
  return bar;
}

// 🔁 opens a small menu: Repost (or Undo repost), and Quote.
function repostMenu(post, focusPrefix) {
  const reposted = youReposted(post.id);
  const count = repostCount(post.id);
  const menu = element("details", "post-menu repost-menu");
  const summary = element("summary", "action action-repost" + (reposted ? " active" : ""));
  summary.dataset.focus = focusPrefix + "repost-" + post.id;
  summary.setAttribute("aria-label", t(reposted ? "action.reposted" : "action.repost") + (count ? " (" + count + ")" : ""));
  summary.append(icon("repost"), element("span", "action-count", count > 0 ? String(count) : ""));
  const list = element("div", "post-menu-list post-menu-list-left");
  list.append(
    menuItem("repost", t(reposted ? "action.undoRepost" : "action.repost"), () => handlers.repost(post.id, reposted), menu),
    menuItem("edit", t("action.quote"), () => handlers.quote(post.id), menu));
  menu.append(summary, list);
  return menu;
}

function menuItem(iconName, words, onClick, menu, danger = false) {
  const item = element("button", "post-menu-item" + (danger ? " danger" : ""));
  item.type = "button";
  item.append(icon(iconName), document.createTextNode(words));
  item.addEventListener("click", () => {
    menu.open = false;
    onClick();
  });
  return item;
}

function actionButton(focusPrefix, postId, iconName, active, count, label, onClick) {
  const button = element("button", "action action-" + iconName + (active ? " active" : ""));
  button.type = "button";
  button.dataset.focus = focusPrefix + iconName + "-" + postId;   // so the keyboard stays here after a redraw
  button.setAttribute("aria-label", label + (count ? " (" + count + ")" : ""));
  if (iconName === "heart" || iconName === "bookmark") {
    button.setAttribute("aria-pressed", active);
  }
  button.append(icon(iconName, active), element("span", "action-count", count > 0 ? String(count) : ""));
  button.addEventListener("click", onClick);
  return button;
}

// "⋯" on your own posts: Edit and Delete. <details> opens and closes without any JavaScript.
function ownMenu(post) {
  const menu = element("details", "post-menu");
  const summary = element("summary", "post-menu-button", "⋯");
  summary.setAttribute("aria-label", t("action.more"));
  const list = element("div", "post-menu-list");
  list.append(menuItem("edit", t("action.edit"), () => handlers.edit(post.id), menu),
              menuItem("trash", t("action.delete"), () => handlers.remove(post.id), menu, true));
  menu.append(summary, list);
  return menu;
}

// A post and, under it, its replies, oldest first, each with their own replies.
export function thread(post) {
  const holder = element("div", "thread");
  holder.append(postCard(post));
  const replies = repliesTo(post.id).filter(isShown);
  if (replies.length > 0) {
    const list = element("div", "thread-replies");
    for (const reply of replies) {
      list.append(thread(reply));
    }
    holder.append(list);
  }
  return holder;
}

// A grey line for an empty screen.
export function emptyNote(title, text) {
  const note = element("div", "empty");
  note.append(element("p", "empty-title", title));
  if (text) {
    note.append(element("p", "empty-text", text));
  }
  return note;
}
