// Your settings, kept in this browser (localStorage): the colours (System, Light or Dark).
// They are only about how the page looks, so the server never hears of them.
// Every read and write is wrapped in try, because some browsers keep nothing (a private window).

const THEME_KEY = "timeline-theme";
export const THEMES = ["system", "light", "dark"];

function load(key, fallback) {
  try {
    return localStorage.getItem(key) || fallback;
  } catch (error) {
    return fallback;
  }
}

function save(key, value) {
  try {
    localStorage.setItem(key, value);
  } catch (error) {
    // Nothing kept: the setting lasts until the page is closed.
  }
}

// "system": follow the computer. "light" or "dark": always that.
export function currentTheme() {
  const theme = load(THEME_KEY, "system");
  return THEMES.includes(theme) ? theme : "system";
}

export function setTheme(theme) {
  if (theme === "system") {
    delete document.documentElement.dataset.theme;   // the stylesheet follows the computer again
  } else {
    document.documentElement.dataset.theme = theme;
  }
  save(THEME_KEY, theme);
}

// System → Light → Dark → System …
export function nextTheme() {
  return THEMES[(THEMES.indexOf(currentTheme()) + 1) % THEMES.length];
}
