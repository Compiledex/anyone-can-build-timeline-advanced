// Everything this window knows, in one place. Every screen is drawn from it.
// When something changes, call changed(), and the screen is drawn again.

export const state = {
  me: null,               // the logged-in person's name, or null when nobody is logged in
  bio: "",                // their bio
  avatar: null,           // the address of their picture, or null
  people: new Map(),      // everyone, by name in small letters: { name, avatar }
  following: new Set(),   // the names they follow, in small letters
  posts: new Map(),       // every post, by id, as the server sent it
  lastId: 0,              // the id of the newest post this window has
  replies: new Map(),     // post id → the replies to it, oldest first
  likes: new Map(),       // post id → { likes, you_liked }
  bookmarks: [],          // the ids of the posts you saved, the latest first
  unreadNotifications: 0, // how many notifications you have not seen yet
  notifications: [],      // your notifications, newest first, when the Notifications page is open
  unreadMessages: 0,      // how many messages you have not read yet
  conversations: [],      // everyone you have messages with, when the Messages page is open
  chat: null,             // the conversation on screen: { with, messages }
  profile: null,          // the profile on screen, as the server sent it
  search: null,           // what the search on screen found: { query, post_ids, people } or { query, error }
  sidebar: { trends: [], suggestions: [] },   // what is trending, and who to follow
};

const listeners = [];

export function onChange(listener) {
  listeners.push(listener);
}

export function changed() {
  for (const listener of listeners) {
    listener();
  }
}

// Names are the same whatever their capitals.
function same(a, b) {
  return a.toLowerCase() === b.toLowerCase();
}

export function setMe(person) {
  state.me = person.name;
  state.bio = person.bio || "";
  state.avatar = person.avatar || null;
  state.unreadNotifications = person.unread_notifications || 0;
  state.unreadMessages = person.unread_messages || 0;
  state.following = new Set(person.following.map((name) => name.toLowerCase()));
}

export function setPeople(list) {
  state.people = new Map(list.map((person) => [person.name.toLowerCase(), person]));
}

// The address of someone's picture, or null.
export function avatarOf(name) {
  const person = state.people.get(name.toLowerCase());
  return person ? person.avatar : null;
}

export function isMe(name) {
  return state.me !== null && same(name, state.me);
}

export function isFollowed(name) {
  return state.following.has(name.toLowerCase());
}

// New posts, oldest first. A reply always comes after the post it answers.
export function addPosts(posts) {
  for (const post of posts) {
    state.posts.set(post.id, post);
    state.lastId = Math.max(state.lastId, post.id);
    if (post.reply_to !== null) {
      if (!state.replies.has(post.reply_to)) {
        state.replies.set(post.reply_to, []);
      }
      state.replies.get(post.reply_to).push(post);
    }
  }
}

// An edited or deleted post: keep the new version, in the same places.
export function updatePost(post) {
  const old = state.posts.get(post.id);
  if (!old) {
    return;
  }
  Object.assign(old, post);
}

export function setLikes(counts) {
  state.likes = new Map(counts.map((count) => [count.post_id, count]));
}

export function isBookmarked(postId) {
  return state.bookmarks.includes(postId);
}

export function likesOf(postId) {
  return state.likes.get(postId) || { likes: 0, you_liked: false };
}

export function repliesTo(postId) {
  return state.replies.get(postId) || [];
}

export function replyCount(postId) {
  return repliesTo(postId).filter((reply) => !reply.deleted_at).length;
}

// A deleted post is still shown when replies under it are, so that they keep their place.
// A repost is shown while it and the post it shares are both there.
export function isShown(post) {
  if (post.repost_of !== null) {
    const original = state.posts.get(post.repost_of);
    return !post.deleted_at && original !== undefined && !original.deleted_at;
  }
  return !post.deleted_at || repliesTo(post.id).some(isShown);
}

// How many times a post was reposted or quoted (not counting undone or deleted ones).
export function repostCount(postId) {
  let count = 0;
  for (const post of state.posts.values()) {
    if ((post.repost_of === postId || post.quote_of === postId) && !post.deleted_at) {
      count += 1;
    }
  }
  return count;
}

export function youReposted(postId) {
  for (const post of state.posts.values()) {
    if (post.repost_of === postId && !post.deleted_at && isMe(post.author)) {
      return true;
    }
  }
  return false;
}

export function byAuthor(post, name) {
  return same(post.author, name);
}

// Newest first.
export function newestFirst(posts) {
  return [...posts].sort((a, b) => b.id - a.id);
}
