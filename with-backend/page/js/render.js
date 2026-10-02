// Drawing things: an avatar, a post card, a thread of replies.
// Everything a user typed is put on the page with textContent, never innerHTML,
// so a post is always shown as words and can never run code on the page.

import { icon } from "./icons.js";
import { avatarColour, fullTime, initials, postLink, profileLink, shortTime } from "./format.js";
import { avatarOf, isMe, isShown, likesOf, replyCount, repliesTo, state } from "./state.js";

// What the buttons on a post do. main.js fills these in.
export const handlers = {
  reply: (postId) => {},
  like: (postId) => {},
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

// A post's words.
export function postText(text) {
  return document.createTextNode(text);
}

// One post. options.preview: no buttons (inside a window). options.big: the post on its own page.
// options.replyingTo: say which post this one answers.
export function postCard(post, options = {}) {
  const card = element("article", "post-card" + (options.big ? " post-card-big" : ""));
  card.dataset.id = post.id;

  if (post.deleted_at) {
    card.classList.add("deleted");
    card.append(element("p", "post-deleted-text", "This post was deleted."));
    opensOnClick(card, post, options);   // its replies are on its own page
    return card;
  }

  const main = element("div", "post-main");
  const head = element("div", "post-head");
  head.append(link(profileLink(post.author), "post-author", post.author));
  if (!options.big) {
    const time = link(postLink(post.id), "post-time", shortTime(post.posted_at));
    time.title = fullTime(post.posted_at);
    head.append(element("span", "post-dot", "·"), time);
  }
  if (post.edited_at) {
    head.append(element("span", "post-edited", "· edited"));
  }
  if (!options.preview && isMe(post.author)) {
    head.append(ownMenu(post));
  }
  main.append(head);

  if (options.replyingTo && post.reply_to !== null) {
    const parent = state.posts.get(post.reply_to);
    if (parent && !parent.deleted_at) {
      const line = element("p", "post-replying", "Replying to ");
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
    const picture = element("img", "post-picture");
    picture.src = post.picture;
    picture.alt = "A picture posted by " + post.author;
    picture.loading = "lazy";
    main.append(picture);
  }

  if (options.big) {
    main.append(element("p", "post-full-time", fullTime(post.posted_at)));
  }
  if (!options.preview) {
    main.append(actionBar(post));
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

// The row of buttons under a post: reply and like, each with its count.
function actionBar(post) {
  const bar = element("div", "post-actions");
  const replies = replyCount(post.id);
  bar.append(actionButton(post.id, "reply", false, replies, "Reply", () => handlers.reply(post.id)));
  const likes = likesOf(post.id);
  bar.append(actionButton(post.id, "heart", likes.you_liked, likes.likes,
                          likes.you_liked ? "Unlike" : "Like", () => handlers.like(post.id)));
  return bar;
}

function actionButton(postId, iconName, active, count, label, onClick) {
  const button = element("button", "action action-" + iconName + (active ? " active" : ""));
  button.type = "button";
  button.dataset.focus = iconName + "-" + postId;   // so the keyboard stays here after a redraw
  button.setAttribute("aria-label", label + (count ? " (" + count + ")" : ""));
  if (iconName === "heart") {
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
  summary.setAttribute("aria-label", "More");
  const list = element("div", "post-menu-list");
  const edit = element("button", "post-menu-item");
  edit.type = "button";
  edit.append(icon("edit"), document.createTextNode("Edit"));
  edit.addEventListener("click", () => {
    menu.open = false;
    handlers.edit(post.id);
  });
  const remove = element("button", "post-menu-item danger");
  remove.type = "button";
  remove.append(icon("trash"), document.createTextNode("Delete"));
  remove.addEventListener("click", () => {
    menu.open = false;
    handlers.remove(post.id);
  });
  list.append(edit, remove);
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
