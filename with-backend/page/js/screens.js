// The screens. Each one returns what the middle column shows:
// { title, breadcrumb, tabs, nodes }. main.js puts it on the page.

import { icon } from "./icons.js";
import { exploreLink, monthYear, profileLink } from "./format.js";
import { avatar, element, emptyNote, link, postCard, thread } from "./render.js";
import { byAuthor, isFollowed, isMe, isShown, newestFirst, repliesTo, state } from "./state.js";

// What the buttons on a profile do. main.js fills these in.
export const profileHandlers = {
  follow: () => {},
  edit: () => {},
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
      ? emptyNote("Nothing here yet", "When people you follow post, it shows up here. Open a profile and press Follow.")
      : emptyNote("Nothing here yet", "Be the first to post."));
  }
  return {
    title: "Home",
    breadcrumb: ["Timeline", "Home"],
    tabs: state.me === null ? [] : [
      { label: "For everyone", href: "#/", current: !onlyFollowing },
      { label: "Following", href: "#/following", current: onlyFollowing },
    ],
    nodes: nodes,
  };
}

// ---- Bookmarks: the posts you saved. Only you see them. ----

export function bookmarksScreen() {
  const posts = state.bookmarks.map((id) => state.posts.get(id)).filter((post) => post && !post.deleted_at);
  const nodes = posts.map((post) => postCard(post, { replyingTo: true }));
  if (state.me === null) {
    nodes.push(emptyNote("Log in to see your bookmarks"));
  } else if (nodes.length === 0) {
    nodes.push(emptyNote("Save posts for later", "Press 🔖 under a post to save it here. Only you can see your bookmarks."));
  }
  return { title: "Bookmarks", breadcrumb: ["Timeline", "Bookmarks"], tabs: [], nodes: nodes };
}

// ---- Explore: search for posts, people and #tags ----

export function exploreScreen(address) {
  const nodes = [];
  const query = address.query;
  const title = query.startsWith("#") && query.length > 1 ? query : "Explore";
  if (query === "") {
    nodes.push(emptyNote("Search Timeline", "Find posts, people and #tags. Try #kyoto or #kanji."));
  } else if (!state.search || state.search.query !== query) {
    nodes.push(emptyNote("Searching…"));
  } else if (state.search.error) {
    nodes.push(emptyNote("Nothing to search for", state.search.error));
  } else {
    if (state.search.people.length > 0) {
      nodes.push(element("h2", "section-title", "People"));
      nodes.push(...state.search.people.map(personRow));
    }
    const posts = state.search.post_ids.map((id) => state.posts.get(id)).filter((post) => post && isShown(post));
    if (posts.length > 0) {
      nodes.push(element("h2", "section-title", "Posts"));
      nodes.push(...posts.map((post) => postCard(post, { replyingTo: true })));
    }
    if (nodes.length === 0) {
      nodes.push(emptyNote("No results for " + query, "Try other words, or a #tag."));
    }
  }
  return { title: title, breadcrumb: ["Timeline", "Explore"], tabs: [], nodes: nodes };
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
  back.append(icon("back"), document.createTextNode("Back to the timeline"));
  if (!post) {
    return { title: "Post", breadcrumb: ["Timeline", "Post"], tabs: [], nodes: [back, emptyNote("This post does not exist")] };
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
  return { title: "Post", breadcrumb: ["Timeline", "Post"], tabs: [], nodes: nodes };
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
      address.tab === "replies" ? name + " has not replied to anyone yet" : name + " has not posted yet")]));
  }
  return {
    title: name,
    breadcrumb: ["Timeline", "Profile"],
    tabs: person ? [
      { label: "Posts", href: profileLink(name), current: address.tab !== "replies" },
      { label: "Replies", href: profileLink(name, "replies"), current: address.tab === "replies" },
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
    const edit = element("button", "button button-outline", "Edit profile");
    edit.type = "button";
    edit.dataset.focus = "edit-profile";
    edit.addEventListener("click", profileHandlers.edit);
    top.append(edit);
  } else if (person && state.me !== null) {
    const follow = element("button", person.you_follow ? "button button-outline" : "button",
                           person.you_follow ? "Following" : "Follow");
    follow.type = "button";
    follow.dataset.focus = "follow";
    if (person.you_follow) {
      follow.setAttribute("aria-label", "Unfollow " + person.name);
    }
    follow.addEventListener("click", profileHandlers.follow);
    top.append(follow);
  }
  header.append(top);
  header.append(element("h2", "profile-name", name));
  header.append(element("p", "profile-handle", "@" + name));
  if (!person) {
    header.append(element("p", "profile-facts", state.profile === false ? "There is no one called " + name + "." : ""));
    return header;
  }
  if (person.bio) {
    header.append(element("p", "profile-bio", person.bio));
  }
  const joined = element("p", "profile-facts");
  joined.append(icon("calendar"), document.createTextNode("Joined " + monthYear(person.joined_at)));
  header.append(joined);
  const numbers = element("p", "profile-numbers");
  for (const [count, word] of [[person.following, "Following"], [person.followers, person.followers === 1 ? "Follower" : "Followers"], [person.posts, person.posts === 1 ? "Post" : "Posts"]]) {
    const pair = element("span", "profile-number");
    pair.append(element("strong", "", String(count)), document.createTextNode(" " + word));
    numbers.append(pair);
  }
  header.append(numbers);
  return header;
}

// ---- The sidebar on the right ----

export function sidebar(openLogin) {
  const nodes = [];
  if (state.me === null) {
    const box = element("section", "side-box");
    box.append(element("h2", "side-title", "New to Timeline?"));
    box.append(element("p", "side-text", "Sign up to post, reply, like and follow."));
    const signUp = element("button", "button button-wide", "Sign up");
    signUp.type = "button";
    signUp.addEventListener("click", () => openLogin("signup"));
    const logIn = element("button", "button button-wide button-outline", "Log in");
    logIn.type = "button";
    logIn.addEventListener("click", () => openLogin("login"));
    box.append(signUp, logIn);
    nodes.push(box);
  } else {
    const box = element("section", "side-box");
    box.append(element("h2", "side-title", "You follow"));
    const names = [...state.posts.values()].map((post) => post.author)
      .filter((name, index, all) => isFollowed(name) && all.indexOf(name) === index);
    if (names.length === 0) {
      box.append(element("p", "side-text", "Nobody yet. Open a profile and press Follow."));
    }
    for (const name of names.sort((a, b) => a.localeCompare(b))) {
      const row = link(profileLink(name), "side-person");
      row.append(avatar(name, "small", false), element("span", "side-person-name", name));
      box.append(row);
    }
    nodes.push(box);
  }
  const about = element("p", "side-about",
    "Timeline · a class project. Colours and fonts after the Kansai Gaidai Asian Studies Program site.");
  nodes.push(about);
  return nodes;
}
