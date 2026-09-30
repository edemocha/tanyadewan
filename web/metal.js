// Liquid-metal rings (metal-fx by Jakub Antalik, MIT) on the send button and "Soalan baru".
// Progressive enhancement: the plain buttons from app.js keep working; this module mounts a metal copy next to
// each one only when React, metal-fx and WebGL2 are all available, then hides the plain one. The copy mirrors
// the original's disabled state and forwards clicks, so app.js needs no changes.
import { createElement as h, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import { MetalFx, MetalText, isMetalFxSupported, useMetalBend, useMetalTextReflection } from "metal-fx";

const PRESET = "silver"; // cool steel: the one that suits a black-and-white UI
const appTheme = () => (document.documentElement.dataset.theme === "dark" ? "dark" : "light");

function useAppTheme() {
  const [theme, setTheme] = useState(appTheme);
  useEffect(() => {
    const o = new MutationObserver(() => setTheme(appTheme()));
    o.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => o.disconnect();
  }, []);
  return theme;
}

function useMirroredDisabled(original) {
  const [disabled, setDisabled] = useState(original.disabled);
  useEffect(() => {
    const o = new MutationObserver(() => setDisabled(original.disabled));
    o.observe(original, { attributes: true, attributeFilter: ["disabled"] });
    return () => o.disconnect();
  }, [original]);
  return disabled;
}

function copyOf(original, disabled) {
  return h("button", {
    type: original.type,
    className: original.dataset.metalClass, // captured before the original was hidden
    disabled,
    "aria-label": original.getAttribute("aria-label") || undefined,
    // a submit button submits its own form natively; anything else forwards the click to the original
    onClick: original.type === "submit" ? undefined : (e) => { e.preventDefault(); original.click(); },
    dangerouslySetInnerHTML: { __html: original.innerHTML },
  });
}

function MetalCircle({ original }) {
  const theme = useAppTheme();
  const disabled = useMirroredDisabled(original);
  const ref = useRef(null);
  useMetalBend(ref); // the ring dents towards the cursor
  return h(MetalFx, { ref, preset: PRESET, variant: "circle", theme, innerShadow: true, strength: disabled ? 0.35 : 1 },
    copyOf(original, disabled));
}

function MetalPill({ original }) {
  const theme = useAppTheme();
  const disabled = useMirroredDisabled(original);
  return h(MetalFx, { preset: PRESET, variant: "button", theme, strength: 0.9 }, copyOf(original, disabled));
}

// Logo: "Dewan." in metal; "Tanya" above it catches the reflection.
function MetalLogo({ tanya, size }) {
  const theme = useAppTheme();
  const tanyaRef = useRef(tanya);
  useMetalTextReflection(tanyaRef);
  return h(MetalText, {
    key: theme, // redraw with the other tuning when the theme flips
    font: `500 ${size}px/1 "Instrument Sans", sans-serif`,
    // the palette's text-primary token for the current theme (tokens.css), so the logo matches body text
    color: getComputedStyle(document.documentElement).getPropertyValue("--text-primary").trim(),
    strength: theme === "dark" ? 0.9 : 0.45, // on a light canvas full metal washes the ink out; keep it legible
    reflectionTargets: [{ ref: tanyaRef, strength: 0.64 }],
  }, "Dewan.");
}

function mountLogo(logo) {
  const plain = logo.querySelector(".l2");
  const tanya = logo.querySelector(".l1");
  if (!plain || !tanya || plain.dataset.metal) return;
  const size = parseFloat(getComputedStyle(plain).fontSize) || 22;
  const host = document.createElement("span");
  host.className = "l2 metal-l2";
  host.setAttribute("aria-hidden", "true"); // the logo link keeps its aria-label
  plain.after(host);
  createRoot(host).render(h(MetalLogo, { tanya, size }));
  plain.dataset.metal = "on";
  plain.classList.add("metal-replaced");
}

function mount(original, Component, hostClass) {
  if (!original || original.dataset.metal) return;
  original.dataset.metalClass = original.className;
  const host = document.createElement("span");
  host.className = `metal-host ${hostClass}`;
  original.after(host);
  createRoot(host).render(h(Component, { original }));
  original.dataset.metal = "on";
  original.classList.add("metal-replaced");
}

try {
  if (isMetalFxSupported()) {
    mount(document.querySelector(".composer .send"), MetalCircle, "metal-send");
    mount(document.querySelector("#new-chat"), MetalPill, "metal-new");
    // metal glyphs are drawn on a canvas: wait for the logo font, or they'd render in a fallback font
    document.fonts.ready.then(() => document.querySelectorAll(".logo").forEach(mountLogo));
  }
} catch (err) {
  console.warn("metal-fx unavailable, keeping plain buttons:", err);
}
