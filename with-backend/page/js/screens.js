// The screens. Each one returns what the middle column shows:
// { title, breadcrumb, tabs, nodes }. main.js puts it on the page.

import { icon } from "./icons.js";
import { t, tCount } from "./strings.js";
import { exploreLink, fullTime, messagesLink, monthYear, postLink, profileLink, shortTime } from "./format.js";
import { avatar, element, emptyNote, link, postCard, thread } from "./render.js";
import { byAuthor, isFollowed, isMe, isShown, newestFirst, repliesTo, state } from "./state.js";

// What the buttons on a profile do. main.js fills these in.
export const profileHandlers = {
  follow: () => {},
  edit: () => {},
};

// What the Follow buttons in the sidebar do. main.js fills this in.
export const sidebarHandlers = {
  follow: (name) => {},
};

// ---- Home ----

export function homeScreen(address) {
  const onlyFollowing = address.tab === "following" && state.me !== null;
  let posts = [...state.posts.values()].filter((post) => post.reply_to === null && isShown(post));
  if (onlyFollowing) {
    posts = posts.filter((post) => isMe(post.author) || isFollowed(post.author));
  }
  const nodes = newestFirst(posts).map((post) => postCard(post));
  if (nodes.length === 0) {
    nodes.push(onlyFollowing
      ? emptyNote(t("empty.nothingYet"), t("empty.followingText"))
      : emptyNote(t("empty.nothingYet"), t("empty.beFirst")));
  }
  return {
    title: t("nav.home"),
    breadcrumb: [t("app.name"), t("nav.home")],
    tabs: state.me === null ? [] : [
      { label: t("tab.everyone"), href: "#/", current: !onlyFollowing },
      { label: t("tab.following"), href: "#/following", current: onlyFollowing },
    ],
    nodes: nodes,
  };
}

// ---- Messages: your conversations, and one conversation ----

export function messagesScreen(address) {
  if (address.with) {
    return chatScreen(address.with);
  }
  const nodes = state.conversations.map((talk) => {
    const row = link(messagesLink(talk.name), "conversation" + (talk.unread > 0 ? " unread" : ""));
    const words = element("span", "conversation-words");
    const top = element("span", "conversation-top");
    top.append(element("span", "conversation-name", talk.name),
               element("span", "conversation-time", " · " + shortTime(talk.sent_at)));
    words.append(top, element("span", "conversation-last", (talk.from_me ? t("messages.you") : "") + talk.text));
    row.append(avatar(talk.name, "normal", false), words);
    if (talk.unread > 0) {
      row.append(element("span", "conversation-dot", String(talk.unread)));
    }
    return row;
  });
  if (nodes.length === 0) {
    nodes.push(emptyNote(t("messages.welcome"), t("messages.welcomeText")));
  }
  return { title: t("nav.messages"), breadcrumb: [t("app.name"), t("nav.messages")], tabs: [], nodes: nodes };
}

function chatScreen(name) {
  const back = link(messagesLink(), "back-link");
  back.append(icon("back"), document.createTextNode(t("messages.all")));
  const nodes = [back];
  const chat = state.chat && state.chat.with.toLowerCase() === name.toLowerCase() ? state.chat : null;
  const shownName = chat ? chat.with : name;
  if (chat === null) {
    nodes.push(emptyNote(state.chat === false ? t("noOne", { name: name }) : t("loading")));
  } else {
    const who = link(profileLink(shownName), "chat-who");
    who.append(avatar(shownName, "big", false), element("span", "chat-who-name", shownName),
               element("span", "chat-who-handle", "@" + shownName));
    nodes.push(who);
    const list = element("div", "chat");
    chat.messages.forEach((message, index) => {
      const bubble = element("div", "message" + (message.from_me ? " mine" : ""));
      bubble.append(element("p", "message-text", message.text));
      const isLast = index === chat.messages.length - 1;
      const time = element("p", "message-time", shortTime(message.sent_at));
      time.title = fullTime(message.sent_at);
      if (isLast && message.from_me && message.read) {
        time.append(document.createTextNode(" · " + t("messages.seen")));
      }
      bubble.append(time);
      list.append(bubble);
    });
    if (chat.messages.length === 0) {
      list.append(element("p", "chat-empty", t("messages.sayHello", { name: shownName })));
    }
    nodes.push(list);
  }
  return { title: shownName, breadcrumb: [t("app.name"), t("nav.messages")], tabs: [], nodes: nodes };
}

// ---- Notifications: what happened to you ----

// The icon for each kind of notification. The words are "notif.like" and so on in strings.js:
// " liked your post" in English, "さんがあなたのポストをいいねしました" in Japanese, after the name.
const TOLD_ICON = { like: "heart", repost: "repost", quote: "edit", reply: "reply", mention: "mail", follow: "user" };

export function notificationsScreen() {
  const nodes = state.notifications.map(notificationRow);
  if (nodes.length === 0) {
    nodes.push(emptyNote(t("notif.nothing"), t("notif.nothingText")));
  }
  return { title: t("nav.notifications"), breadcrumb: [t("app.name"), t("nav.notifications")], tabs: [], nodes: nodes };
}

function notificationRow(told) {
  const iconName = TOLD_ICON[told.kind];
  const row = link(told.kind === "follow" ? profileLink(told.actor) : postLink(told.post_id),
                   "notification notification-" + told.kind + (told.read ? "" : " unread"));
  const side = element("span", "notification-icon");
  side.append(icon(iconName, told.kind === "like"));
  const main = element("span", "notification-main");
  main.append(avatar(told.actor, "small", false));
  const line = element("span", "notification-line");
  line.append(element("strong", "notification-actor", told.actor), document.createTextNode(t("notif." + told.kind)),
              element("span", "notification-time", " · " + shortTime(told.created_at)));
  main.append(line);
  const post = told.post_id === null ? null : state.posts.get(told.post_id);
  if (post && post.text) {
    main.append(element("span", "notification-text", post.text));
  }
  row.append(side, main);
  return row;
}

// ---- Bookmarks: the posts you saved. Only you see them. ----

export function bookmarksScreen() {
  const posts = state.bookmarks.map((id) => state.posts.get(id)).filter((post) => post && !post.deleted_at);
  const nodes = posts.map((post) => postCard(post, { replyingTo: true }));
  if (state.me === null) {
    nodes.push(emptyNote(t("bookmarks.logIn")));
  } else if (nodes.length === 0) {
    nodes.push(emptyNote(t("bookmarks.empty"), t("bookmarks.emptyText")));
  }
  return { title: t("nav.bookmarks"), breadcrumb: [t("app.name"), t("nav.bookmarks")], tabs: [], nodes: nodes };
}

// ---- Explore: search for posts, people and #tags ----

export function exploreScreen(address) {
  const nodes = [];
  const query = address.query;
  const title = query.startsWith("#") && query.length > 1 ? query : t("nav.explore");
  if (query === "") {
    if (state.sidebar.trends.length > 0) {
      nodes.push(element("h2", "section-title", t("explore.trendingWeek")));
      nodes.push(...state.sidebar.trends.map((trend, index) => trendRow(trend, index, "trend-row-big")));
    } else {
      nodes.push(emptyNote(t("explore.searchTitle"), t("explore.searchText")));
    }
  } else if (!state.search || state.search.query !== query) {
    nodes.push(emptyNote(t("explore.searching")));
  } else if (state.search.error) {
    nodes.push(emptyNote(t("explore.nothing"), state.search.error));
  } else {
    if (state.search.people.length > 0) {
      nodes.push(element("h2", "section-title", t("explore.people")));
      nodes.push(...state.search.people.map(personRow));
    }
    const posts = state.search.post_ids.map((id) => state.posts.get(id)).filter((post) => post && isShown(post));
    if (posts.length > 0) {
      nodes.push(element("h2", "section-title", t("explore.posts")));
      nodes.push(...posts.map((post) => postCard(post, { replyingTo: true })));
    }
    if (nodes.length === 0) {
      nodes.push(emptyNote(t("explore.noResults", { query: query }), t("explore.noResultsText")));
    }
  }
  return { title: title, breadcrumb: [t("app.name"), t("nav.explore")], tabs: [], nodes: nodes };
}

// A person in a list: avatar, name, @name and bio, the whole row a link to their profile.
export function personRow(person) {
  const row = link(profileLink(person.name), "person-row");
  const words = element("span", "person-words");
  words.append(element("span", "person-name", person.name), element("span", "person-handle", "@" + person.name));
  if (person.bio) {
    words.append(element("span", "person-bio", person.bio));
  }
  row.append(avatar(person.name, "normal", false), words);
  return row;
}

// ---- One post, with the posts it answers above it and its replies below ----

export function postScreen(address) {
  let post = state.posts.get(address.id);
  if (post && post.repost_of !== null) {
    post = state.posts.get(post.repost_of);   // a repost's page is the page of the post it shares
  }
  const back = link("#/", "back-link");
  back.append(icon("back"), document.createTextNode(t("post.back")));
  if (!post) {
    return { title: t("post.title"), breadcrumb: [t("app.name"), t("post.title")], tabs: [],
             nodes: [back, emptyNote(t("post.missing"))] };
  }
  const above = [];
  for (let parent = state.posts.get(post.reply_to); parent; parent = state.posts.get(parent.reply_to)) {
    above.unshift(postCard(parent));
  }
  const chain = element("div", "chain");
  chain.append(...above);
  const nodes = [back, chain, postCard(post, { big: true })];
  for (const reply of repliesTo(post.id).filter(isShown)) {
    nodes.push(thread(reply));
  }
  return { title: t("post.title"), breadcrumb: [t("app.name"), t("post.title")], tabs: [], nodes: nodes };
}

// ---- A profile ----

export function profileScreen(address) {
  const person = state.profile && state.profile.name.toLowerCase() === address.name.toLowerCase()
    ? state.profile
    : null;
  const name = person ? person.name : address.name;
  const nodes = [profileHeader(name, person)];

  if (person) {
    const theirs = [...state.posts.values()].filter((post) => byAuthor(post, name) && !post.deleted_at && isShown(post));
    const shown = address.tab === "replies"
      ? theirs.filter((post) => post.reply_to !== null)
      : theirs.filter((post) => post.reply_to === null);
    const cards = newestFirst(shown).map((post) => postCard(post, { replyingTo: true }));
    nodes.push(...(cards.length > 0 ? cards : [emptyNote(
      t(address.tab === "replies" ? "profile.notReplied" : "profile.notPosted", { name: name }))]));
  }
  return {
    title: name,
    breadcrumb: [t("app.name"), t("nav.profile")],
    tabs: person ? [
      { label: t("profile.tab.posts"), href: profileLink(name), current: address.tab !== "replies" },
      { label: t("profile.tab.replies"), href: profileLink(name, "replies"), current: address.tab === "replies" },
    ] : [],
    nodes: nodes,
  };
}

// The top of a profile: a navy banner with a gold line, the avatar, the name, the numbers.
function profileHeader(name, person) {
  const header = element("section", "profile");
  header.append(element("div", "profile-banner"));
  const top = element("div", "profile-top");
  top.append(avatar(name, "big", false));
  if (person && isMe(person.name)) {
    const edit = element("button", "button button-outline", t("profile.edit"));
    edit.type = "button";
    edit.dataset.focus = "edit-profile";
    edit.addEventListener("click", profileHandlers.edit);
    top.append(edit);
  } else if (person && state.me !== null) {
    const message = link(messagesLink(person.name), "icon-button icon-button-outline");
    message.setAttribute("aria-label", t("profile.messageName", { name: person.name }));
    message.title = t("profile.message");
    message.append(icon("mail"));
    top.append(message);
    const follow = element("button", person.you_follow ? "button button-outline" : "button",
                           person.you_follow ? t("profile.following") : t("profile.follow"));
    follow.type = "button";
    follow.dataset.focus = "follow";
    if (person.you_follow) {
      follow.setAttribute("aria-label", t("profile.unfollowName", { name: person.name }));
    }
    follow.addEventListener("click", profileHandlers.follow);
    top.append(follow);
  }
  header.append(top);
  header.append(element("h2", "profile-name", name));
  header.append(element("p", "profile-handle", "@" + name));
  if (!person) {
    header.append(element("p", "profile-facts", state.profile === false ? t("noOne", { name: name }) : ""));
    return header;
  }
  if (person.bio) {
    header.append(element("p", "profile-bio", person.bio));
  }
  const joined = element("p", "profile-facts");
  joined.append(icon("calendar"), document.createTextNode(t("profile.joined", { date: monthYear(person.joined_at) })));
  header.append(joined);
  const numbers = element("p", "profile-numbers");
  const counts = [
    [person.following, t("profile.followingCount")],
    [person.followers, tCount("profile.followers", person.followers)],
    [person.posts, tCount("profile.posts", person.posts)],
  ];
  for (const [count, word] of counts) {
    const pair = element("span", "profile-number");
    pair.append(element("strong", "", String(count)), document.createTextNode(" " + word));
    numbers.append(pair);
  }
  header.append(numbers);
  return header;
}

// ---- The sidebar on the right ----

// One trending #tag: its place, the tag, and how many posts have it.
function trendRow(trend, index, className = "") {
  const row = link(exploreLink("#" + trend.tag), "trend-row " + className);
  row.append(element("span", "trend-place", t("side.trending", { place: index + 1 })),
             element("span", "trend-tag", "#" + trend.tag),
             element("span", "trend-count", tCount("side.posts", trend.posts)));
  return row;
}

export function sidebar(openLogin) {
  const nodes = [];
  if (state.me === null) {
    const box = element("section", "side-box");
    box.append(element("h2", "side-title", t("side.newTitle")));
    box.append(element("p", "side-text", t("side.newText")));
    const signUp = element("button", "button button-wide", t("login.signUp"));
    signUp.type = "button";
    signUp.addEventListener("click", () => openLogin("signup"));
    const logIn = element("button", "button button-wide button-outline", t("login.logIn"));
    logIn.type = "button";
    logIn.addEventListener("click", () => openLogin("login"));
    box.append(signUp, logIn);
    nodes.push(box);
  }
  if (state.sidebar.trends.length > 0) {
    const box = element("section", "side-box");
    box.append(element("h2", "side-title", t("side.happening")));
    box.append(...state.sidebar.trends.map((trend, index) => trendRow(trend, index)));
    nodes.push(box);
  }
  if (state.sidebar.suggestions.length > 0) {
    const box = element("section", "side-box");
    box.append(element("h2", "side-title", t("side.whoToFollow")));
    for (const person of state.sidebar.suggestions) {
      const row = element("div", "side-person");
      const who = link(profileLink(person.name), "side-person-link");
      const words = element("span", "side-person-words");
      words.append(element("span", "side-person-name", person.name),
                   element("span", "side-person-handle", "@" + person.name));
      who.append(avatar(person.name, "normal", false), words);
      row.append(who);
      if (state.me !== null) {
        const follow = element("button", "button button-small", t("side.follow"));
        follow.type = "button";
        follow.dataset.focus = "side-follow-" + person.name;
        follow.setAttribute("aria-label", t("side.followName", { name: person.name }));
        follow.addEventListener("click", () => sidebarHandlers.follow(person.name));
        row.append(follow);
      }
      box.append(row);
    }
    nodes.push(box);
  }
  const about = element("p", "side-about", t("side.about"));
  nodes.push(about);
  return nodes;
}
