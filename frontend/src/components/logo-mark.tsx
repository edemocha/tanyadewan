import { useId } from "react";

// The TanyaDewan mark, traced from the owner's artwork: a roof band and the body under it, each folded along one
// vertical line into a lit face and a shaded face. The ink is currentColor and the fold shading fades it towards
// the page background (--bg), so one drawing serves both themes: white with dark folds on black, black with
// light folds on white. Baked copies for use outside the site are in public/logo-on-dark.svg and
// public/logo-on-light.svg; assets/logo-tile.svg feeds scripts/make_favicon.py.
const ROOF =
  "M517 487.2 L517 421.1 Q517 403.1 532.81 394.5 L760 271 L991.85 415.66 Q1019 432.6 1019 464.6 L1019 561.5 Q1019 566.5 1014.67 568.99 L926 620 Q948 611 951 592 L951 471.8 Q951 468.8 948.46 467.21 L760 349 Z";
const BODY =
  "M661 442.5 L760 388 L760 572.4 L913 483.5 L913 574.5 Q913 596.5 894.64 608.62 L760 697.5 L760 572.4 L661 631.4 Z";

export function LogoMark({ className, title }: { className?: string; title?: string }) {
  const id = useId();
  return (
    <svg viewBox="506.5 223 522 522" className={className} role={title ? "img" : undefined} aria-label={title} aria-hidden={title ? undefined : true}>
      <defs>
        <clipPath id={`${id}roof`}>
          <path d={ROOF} />
        </clipPath>
        <clipPath id={`${id}body`}>
          <path d={BODY} />
        </clipPath>
        <linearGradient id={`${id}g1`} gradientUnits="userSpaceOnUse" x1="770" y1="300" x2="1010" y2="570">
          <stop offset="0" stopColor="var(--bg)" stopOpacity=".6" />
          <stop offset="1" stopColor="var(--bg)" stopOpacity=".18" />
        </linearGradient>
        <linearGradient id={`${id}g2`} gradientUnits="userSpaceOnUse" x1="0" y1="400" x2="0" y2="625">
          <stop offset="0" stopColor="var(--bg)" stopOpacity=".1" />
          <stop offset="1" stopColor="var(--bg)" stopOpacity=".5" />
        </linearGradient>
        <linearGradient id={`${id}g3`} gradientUnits="userSpaceOnUse" x1="0" y1="490" x2="0" y2="695">
          <stop offset="0" stopColor="var(--bg)" stopOpacity=".34" />
          <stop offset="1" stopColor="var(--bg)" stopOpacity=".55" />
        </linearGradient>
      </defs>
      <path fill="currentColor" d={`${ROOF} ${BODY}`} />
      <rect x="760" y="250" width="300" height="420" fill={`url(#${id}g1)`} clipPath={`url(#${id}roof)`} />
      <rect x="600" y="370" width="160" height="350" fill={`url(#${id}g2)`} clipPath={`url(#${id}body)`} />
      <rect x="760" y="460" width="200" height="260" fill={`url(#${id}g3)`} clipPath={`url(#${id}body)`} />
    </svg>
  );
}
