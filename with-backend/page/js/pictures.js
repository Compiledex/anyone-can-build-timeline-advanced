// Adding a picture: a button that opens the computer's file chooser, a preview with a ×
// to take the picture out again, and the uploaded picture's id for the post.
// The picture is sent to the server as soon as it is chosen; the post only names its id.

import { uploadPicture } from "./api.js";
import { icon } from "./icons.js";

// The same rules as the server, checked here first so that nobody waits for a refusal.
export const PICTURE_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];
export const MAX_PICTURE = 2 * 1024 * 1024;

// Check a chosen file, and send it. Returns { answer: { id, url } } or { error }.
export async function checkAndUpload(file) {
  if (!PICTURE_TYPES.includes(file.type)) {
    return { error: "Only JPEG, PNG, GIF and WebP pictures are allowed." };
  }
  if (file.size > MAX_PICTURE) {
    return { error: "A picture must be 2 MB or smaller." };
  }
  return uploadPicture(file);
}

// A file chooser that never shows itself; a button opens it.
export function hiddenFileInput() {
  const input = document.createElement("input");
  input.type = "file";
  input.accept = PICTURE_TYPES.join(",");
  input.hidden = true;
  return input;
}

// tools: where the 🖼 button goes. preview: where the chosen picture is shown.
// onChange: called when a picture is added or taken out. onError: called with a reason.
export function picturePicker(tools, preview, onChange, onError) {
  const input = hiddenFileInput();
  const button = document.createElement("button");
  button.type = "button";
  button.className = "icon-button tool";
  button.setAttribute("aria-label", "Add a picture");
  button.title = "Add a picture";
  button.append(icon("image"));
  tools.append(button, input);

  let picture = null;   // { id, url } once uploaded

  function show() {
    preview.replaceChildren();
    if (picture === null) {
      return;
    }
    const image = document.createElement("img");
    image.src = picture.url;
    image.alt = "The picture you added";
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "picture-remove";
    remove.setAttribute("aria-label", "Take the picture out");
    remove.append(icon("close"));
    remove.addEventListener("click", () => {
      picture = null;
      show();
      onChange();
    });
    preview.append(image, remove);
  }

  button.addEventListener("click", () => input.click());
  input.addEventListener("change", async () => {
    const file = input.files[0];
    input.value = "";   // so the same file can be chosen again
    if (!file) {
      return;
    }
    button.disabled = true;
    preview.textContent = "Adding the picture…";
    const { answer, error } = await checkAndUpload(file);
    button.disabled = false;
    if (error) {
      preview.textContent = "";
      onError(error);
      return;
    }
    picture = answer;
    show();
    onChange();
  });

  return {
    get id() {
      return picture ? picture.id : null;
    },
    clear() {
      picture = null;
      show();
    },
    set hidden(hide) {
      button.hidden = hide;
    },
  };
}
