// The icons: simple line drawings, 24 by 24, in the colour of the text around them.
// Each one is a fixed shape written here, never anything a user typed.

const SHAPES = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6h-6v6H4a1 1 0 0 1-1-1z",
  user: "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0",
  feather: "M4 20l4-1L19 8a2.1 2.1 0 0 0-3-3L5 16zM14 7l3 3",
  logout: "M15 4h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4M10 16l-4-4 4-4M6 12h11",
  close: "M6 6l12 12M18 6 6 18",
  back: "M19 12H5M11 18l-6-6 6-6",
  reply: "M21 12a8 8 0 0 1-11.6 7.1L4 20l1.1-4.6A8 8 0 1 1 21 12z",
  heart: "M12 20s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.2a4.3 4.3 0 0 1 7.5 2.6C19.5 15.4 12 20 12 20z",
  repost: "M17 2l3 3-3 3M4 11V9a4 4 0 0 1 4-4h12M7 22l-3-3 3-3M20 13v2a4 4 0 0 1-4 4H4",
  bookmark: "M6 3h12v18l-6-4-6 4z",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM21 21l-5-5",
  bell: "M6 16v-5a6 6 0 1 1 12 0v5l2 2H4zM10 21h4",
  mail: "M3 6h18v12H3zM3 7l9 6 9-6",
  image: "M4 5h16v14H4zM4 16l5-5 4 4 3-3 4 4M15 9.5h.01",
  hash: "M10 3 8 21M16 3l-2 18M4 9h17M3 15h17",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4",
  edit: "M4 20h4L19 9l-4-4L4 16zM13 7l4 4",
  trash: "M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3",
  send: "M4 12 20 4l-5 16-3-7z",
};

// Shapes that are filled in when active: a liked heart, a saved bookmark.
const FILLED = new Set(["heart", "bookmark"]);

export function icon(name, filled = false) {
  const holder = document.createElement("span");
  holder.className = "icon";
  holder.setAttribute("aria-hidden", "true");
  const fill = filled && FILLED.has(name) ? "currentColor" : "none";
  holder.innerHTML =
    `<svg viewBox="0 0 24 24" width="24" height="24" fill="${fill}" stroke="currentColor" ` +
    `stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="${SHAPES[name]}"/></svg>`;
  return holder;
}

// Put the icons into index.html, wherever it says <span data-icon="…">.
export function fillIcons(root = document) {
  for (const place of root.querySelectorAll("[data-icon]")) {
    place.replaceWith(icon(place.dataset.icon));
  }
}
