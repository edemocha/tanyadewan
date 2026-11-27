"use client";

import { useEffect, useRef, useState } from "react";

import { SourcePreview } from "@/components/answer";
import type { Source } from "@/lib/api";
import { MONTHS_MS } from "@/lib/copy";
import { cn } from "@/lib/utils";

const DAY = 86_400_000;
const ms = (iso: string) => Date.parse(`${iso}T00:00:00Z`);
// Dots closer than this would overlap (a dot is 18px), so the later one moves up a row.
const MIN_GAP_PX = 21;
// the axis width assumed until it has been measured: the narrowest phone column
const NARROW_PX = 300;
const ROW_PX = 22;

type Props = {
  sources: Source[];
  cited: Set<number>;
  onCite: (n: number) => void;
  /** the indexed range (from /api/status): the axis spans it, so empty stretches are visible too */
  from?: string | null;
  to?: string | null;
};

/**
 * When the excerpts found for this question were said, on a time axis: one dot per excerpt, placed at its sitting
 * date, numbered like its citation. It plots only the excerpts retrieved for this answer (a handful), never how
 * often a topic came up in the whole record: that needs a count from the backend, and the caption says so.
 * Solid = cited in the answer, outline = found but not cited. No other colour carries meaning.
 */
export function SourceDates({ sources, cited, onCite, from, to }: Props) {
  // how many dots fit side by side depends on the real width of the axis
  const axis = useRef<HTMLOListElement>(null);
  const [width, setWidth] = useState(NARROW_PX);
  useEffect(() => {
    const el = axis.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(e.contentRect.width || NARROW_PX));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const minGapPct = (MIN_GAP_PX / width) * 100;

  const dated = sources.filter((s) => !Number.isNaN(ms(s.date))).sort((a, b) => a.date.localeCompare(b.date) || a.n - b.n);
  // one sitting is not a spread worth drawing
  if (new Set(dated.map((s) => s.date)).size < 2) return null;

  // the axis: the indexed range, widened if a source falls outside it, with a little air at both ends
  const first = Math.min(ms(dated[0].date), from ? ms(from) : Infinity);
  const last = Math.max(ms(dated[dated.length - 1].date), to ? ms(to) : -Infinity);
  const pad = Math.max((last - first) * 0.02, DAY);
  const start = first - pad;
  const span = last + pad - start;
  const pct = (t: number) => ((t - start) / span) * 100;

  // lowest free row for each dot, left to right
  const rowEnds: number[] = [];
  const dots = dated.map((s) => {
    const x = pct(ms(s.date));
    let row = rowEnds.findIndex((end) => x - end >= minGapPct);
    if (row < 0) row = rowEnds.length;
    rowEnds[row] = x;
    return { s, x, row };
  });
  const rows = rowEnds.length;

  // a tick at the start of each month inside the range
  const ticks: { x: number; label: string }[] = [];
  const d = new Date(start);
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() + 1);
  for (; d.getTime() < start + span; d.setUTCMonth(d.getUTCMonth() + 1)) {
    const month = MONTHS_MS[d.getUTCMonth()].slice(0, 3);
    ticks.push({ x: pct(d.getTime()), label: d.getUTCMonth() === 0 || !ticks.length ? `${month} ${d.getUTCFullYear()}` : month });
  }
  // too many months to label each one: keep every second (or third) label, and always the ones carrying a year
  const every = Math.ceil(ticks.length / 8);
  const anyCited = dated.some((s) => cited.has(s.n));

  return (
    <figure className="mb-10">
      <figcaption className="text-[12px] tracking-[0.08em] text-muted-foreground uppercase">Petikan mengikut tarikh sidang</figcaption>

      {/* side room of half a dot, so a dot on the first or last day is not cut off */}
      <div className="mt-4 px-[9px]">
        <ol ref={axis} aria-label="Petikan pada garis masa" className="relative" style={{ height: rows * ROW_PX + 6 }}>
          {dots.map(({ s, x, row }) => (
            <li key={s.n} className="absolute -translate-x-1/2" style={{ left: `${x}%`, bottom: row * ROW_PX + 6 }}>
              <SourcePreview
                src={s}
                chip={
                  <button
                    type="button"
                    onClick={() => onCite(s.n)}
                    aria-label={`Sumber ${s.n}: ${s.speaker}, ${s.date_display}${cited.has(s.n) ? ", dipetik dalam jawapan" : ""}`}
                    className={cn(
                      "grid size-[18px] place-items-center rounded-full border text-[10px] leading-none font-medium tabular transition-transform duration-150 hover:scale-110",
                      cited.has(s.n) ? "border-foreground bg-foreground text-background" : "border-muted-foreground bg-background text-muted-foreground",
                    )}
                  >
                    {s.n}
                  </button>
                }
              />
            </li>
          ))}
        </ol>

        <div aria-hidden className="relative h-7 border-t border-muted-foreground/60">
          {ticks.map((t, i) => (
            <div key={t.x} className="absolute top-0 flex -translate-x-1/2 flex-col items-center" style={{ left: `${t.x}%` }}>
              <span className="h-1.5 w-px bg-muted-foreground/60" />
              {i % every === 0 || t.label.length > 3 ? (
                <span className={cn("mt-1 text-[10.5px] leading-none whitespace-nowrap text-muted-foreground tabular", i % (every * 2) !== 0 && t.label.length <= 3 && "max-sm:hidden")}>
                  {t.label}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      </div>

      <p className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] leading-relaxed text-muted-foreground">
        {anyCited ? (
          <>
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-full bg-foreground" /> dipetik dalam jawapan
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span aria-hidden className="size-2.5 rounded-full border border-muted-foreground" /> ditemui sahaja
            </span>
          </>
        ) : null}
        <span>
          {dated.length} petikan untuk soalan ini, bukan kiraan semua sebutan dalam rekod.
        </span>
      </p>
    </figure>
  );
}
