// Thinking orbs (thinking-orbs by Jakub Antalik, MIT) instead of the three dots while an answer is prepared.
// app.js marks each ".thinking" element with data-state: "searching" (finding Hansard excerpts), then
// "composing" (writing the answer). This module mounts an orb into each one and follows that state.
// Monochrome, and it picks light/dark from <html data-theme> by itself. If this module can't load, the
// dots stay (progressive enhancement).
import { createElement as h } from "react";
import { createRoot } from "react-dom/client";
import { ThinkingOrb } from "thinking-orbs";

const SIZE = 20; // the inline-text tuning; 64 is the chat-avatar tuning
const roots = new WeakMap();

function render(thinking) {
  let entry = roots.get(thinking);
  if (!entry) {
    const host = document.createElement("span");
    host.className = "orb";
    host.setAttribute("aria-hidden", "true");
    thinking.prepend(host);
    entry = { root: createRoot(host) };
    roots.set(thinking, entry);
    thinking.classList.add("orb-on");
  }
  entry.root.render(h(ThinkingOrb, { state: thinking.dataset.state || "searching", size: SIZE, paused: thinking.hidden }));
}

function scan(root) {
  root.querySelectorAll?.(".thinking").forEach(render);
}

const thread = document.getElementById("thread");
new MutationObserver((changes) => {
  for (const c of changes) {
    if (c.type === "attributes") render(c.target);
    else c.addedNodes.forEach((n) => n.nodeType === 1 && scan(n));
  }
}).observe(thread, { childList: true, subtree: true, attributes: true, attributeFilter: ["data-state", "hidden"] });
scan(thread);
