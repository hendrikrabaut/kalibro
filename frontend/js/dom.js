// All text goes through textContent, so titles from a PDF can never inject markup.
export function h(tag, props = {}, ...children) {
  const element = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === null || value === undefined || value === false) continue;
    if (key.startsWith("on")) element.addEventListener(key.slice(2), value);
    else if (key === "class") element.className = value;
    else if (key === "value") element.value = value;
    else if (value === true) element.setAttribute(key, "");
    else element.setAttribute(key, value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    element.append(child);
  }
  return element;
}

export function svg(tag, attributes = {}) {
  const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(attributes)) element.setAttribute(key, value);
  return element;
}

export function fields(form) {
  return Object.fromEntries(new FormData(form).entries());
}

export function toast(message, kind = "info") {
  const box = document.getElementById("toasts");
  if (!box) return;
  const item = h("div", { class: `toast ${kind}` }, message);
  box.append(item);
  setTimeout(() => item.remove(), kind === "error" ? 6000 : 3000);
}

// Runs an action, shows its error as a toast, and returns null on failure.
export async function attempt(action, success) {
  try {
    const result = await action();
    if (success) toast(success, "ok");
    return result;
  } catch (error) {
    toast(error.message, "error");
    return null;
  }
}

export function card(title, ...children) {
  return h("section", { class: "card" }, title ? h("h2", {}, title) : null, ...children);
}
