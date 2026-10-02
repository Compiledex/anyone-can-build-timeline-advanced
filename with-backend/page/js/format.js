// Small helpers for showing things: times, counts, initials, avatar colours, and addresses.

// The server sends times as "2026-10-02 15:42", local time.
export function parseStamp(stamp) {
  const [day, clock] = stamp.split(" ");
  return new Date(day + "T" + clock);
}

// "now", "5m", "3h", "30 Sep", or "30 Sep 2025" for another year.
export function shortTime(stamp) {
  const then = parseStamp(stamp);
  const seconds = (Date.now() - then.getTime()) / 1000;
  if (seconds < 60) {
    return "now";
  }
  if (seconds < 60 * 60) {
    return Math.floor(seconds / 60) + "m";
  }
  if (seconds < 24 * 60 * 60) {
    return Math.floor(seconds / (60 * 60)) + "h";
  }
  const sameYear = then.getFullYear() === new Date().getFullYear();
  return then.toLocaleDateString("en-GB", sameYear
    ? { day: "numeric", month: "short" }
    : { day: "numeric", month: "short", year: "numeric" });
}

// "15:42 · 2 Oct 2026", for a post on its own page, and when you point at a short time.
export function fullTime(stamp) {
  const then = parseStamp(stamp);
  return stamp.split(" ")[1] + " · " +
    then.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

// "October 2026", for "Joined October 2026".
export function monthYear(stamp) {
  return parseStamp(stamp).toLocaleDateString("en-GB", { month: "long", year: "numeric" });
}

// "1 post", "2 posts".
export function plural(count, word) {
  return count + " " + word + (count === 1 ? "" : "s");
}

// The first letter of a name, for an avatar without a picture.
export function initials(name) {
  return Array.from(name)[0].toUpperCase();
}

// Each name always gets the same colour, picked from colours that suit the theme.
const AVATAR_COLOURS = ["#0a5181", "#3b84b0", "#0f2646", "#5b6f95", "#8a6d1f", "#2f6f5e", "#8a3b5c", "#4b4f9c"];

export function avatarColour(name) {
  let sum = 0;
  for (const letter of name.toLowerCase()) {
    sum = (sum * 31 + letter.codePointAt(0)) % 1000003;
  }
  return AVATAR_COLOURS[sum % AVATAR_COLOURS.length];
}

// ---- Addresses ----
// The screen is in the address after "#", so the browser's Back button works:
//   #/              Home, everyone          #/following      Home, people you follow
//   #/@Ben          Ben's posts             #/@Ben/replies   Ben's replies
//   #/post/12       post 12, with its replies
//   #/explore       the search page        #/explore/%23kyoto  what a search for #kyoto found
//   #/bookmarks     your saved posts

export function profileLink(name, tab = "") {
  return "#/@" + encodeURIComponent(name) + (tab ? "/" + tab : "");
}

export function postLink(id) {
  return "#/post/" + id;
}

export function exploreLink(query = "") {
  return "#/explore" + (query ? "/" + encodeURIComponent(query) : "");
}

function decode(part) {
  try {
    return decodeURIComponent(part);
  } catch (error) {
    return part;   // a broken address, like "#/@%": use it as it is
  }
}

// What the address asks for, as { screen, … }.
export function readAddress() {
  const raw = location.hash.replace(/^#\/?/, "");
  if (raw === "explore" || raw.startsWith("explore/")) {
    return { screen: "explore", query: decode(raw.slice("explore/".length)).trim() };
  }
  const parts = raw.split("/").map(decode);
  if (parts[0].startsWith("@") && parts[0].length > 1) {
    return { screen: "profile", name: parts[0].slice(1), tab: parts[1] === "replies" ? "replies" : "posts" };
  }
  if (parts[0] === "bookmarks") {
    return { screen: "bookmarks" };
  }
  if (parts[0] === "post" && /^\d+$/.test(parts[1] || "")) {
    return { screen: "post", id: Number(parts[1]) };
  }
  return { screen: "home", tab: parts[0] === "following" ? "following" : "everyone" };
}
