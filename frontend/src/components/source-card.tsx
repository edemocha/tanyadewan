"use client";

import { ArrowUpRight, BookOpen } from "lucide-react";
import Link from "next/link";
import { forwardRef, Fragment, useEffect, useRef, useState, type ReactNode } from "react";

import { PUBLIC_MODE, type Source } from "@/lib/api";
import { headingCase } from "@/lib/copy";
import { cn } from "@/lib/utils";

// A snippet starts this many characters in or later only when the best-matching sentence lies beyond the first lines.
const VISIBLE_CHARS = 240;

/** Where the collapsed snippet should start: the sentence before the one that matches most of the question's terms. */
function snippetStart(text: string, terms: string[]): number {
  if (!terms.length) return 0;
  let best = { at: 0, score: 0, prev: 0 };
  let prev = 0;
  for (const m of text.matchAll(/[^.!?\n]+[.!?]*\s*/g)) {
    const low = m[0].toLowerCase();
    const score = terms.filter((t) => low.includes(t)).length;
    if (score > best.score) best = { at: m.index ?? 0, score, prev };
    prev = m.index ?? 0;
  }
  return best.score > 0 && best.at > VISIBLE_CHARS ? best.prev : 0;
}

/**
 * The text with the question's terms wrapped in <mark>; the words themselves are never changed.
 * Marked with a thin underline: the serif face has no 500 weight, and a fill would put boxes inside quoted text.
 */
function highlighted(text: string, terms: string[]): ReactNode[] {
  if (!terms.length) return [text];
  const escaped = terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
  const re = new RegExp(`\\b(?:${escaped.join("|")})[\\p{L}\\p{N}]*`, "giu");
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(re)) {
    const i = m.index ?? 0;
    if (i > last) out.push(text.slice(last, i));
    out.push(
      <mark key={i} className="bg-transparent text-foreground underline decoration-muted-foreground decoration-1 underline-offset-4">
        {m[0]}
      </mark>,
    );
    last = i + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/**
 * Where the answer's quotes sit in this text: [start, end) ranges, merged. Matches the way quoteInSource() in
 * answer.tsx compares them ("..." splits a quote into parts, whitespace and apostrophe style are ignored), so a
 * quote that passed that check is found here too. The text itself is never changed.
 */
function quoteRanges(text: string, quotes: string[]): [number, number][] {
  const found: [number, number][] = [];
  for (const q of quotes) {
    for (const part of q.split(/\s*(?:\.\.\.|…)\s*/)) {
      const clean = part.replace(/^[\s.,]+|[\s.,]+$/g, "");
      if (!clean) continue;
      const pattern = clean
        .replace(/[.*+?^${}()|[\]\\]/g, "\\$&")
        .replace(/\s+/g, "\\s+")
        .replace(/['‘’]/g, "['‘’]");
      const m = new RegExp(pattern).exec(text);
      if (m) found.push([m.index, m.index + m[0].length]);
    }
  }
  found.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const r of found) {
    const last = merged[merged.length - 1];
    if (last && r[0] <= last[1]) last[1] = Math.max(last[1], r[1]);
    else merged.push([...r]);
  }
  return merged;
}

/** The start of the sentence that contains position `at`. */
const sentenceStart = (text: string, at: number) => {
  const before = text.slice(0, at);
  const m = /[.!?\n]\s+(?=[^.!?\n]*$)/.exec(before);
  return m ? m.index + m[0].length : 0;
};

// The source number looks exactly like the citation chip in the answer, so the two read as one object.
const NUM = "mt-0.5 inline-grid h-5 min-w-6 shrink-0 place-items-center rounded-md border border-line bg-surface px-1 text-[11px] font-medium tabular text-brand";
const TAG = "rounded-md border border-line bg-surface px-1.5 py-0.5 text-[11px] text-muted-foreground";
const TEXT_BTN = "inline-flex min-h-9 items-center gap-1 rounded-lg text-muted-foreground transition-colors hover:text-foreground";

/**
 * One numbered source: who, when, where in the sitting, the verbatim text, and the PDF page. No card: a row, with
 * whitespace doing the separating. A long speech is indexed in parts that all carry the page the speech STARTS on,
 * so later parts say so.
 */
type CardProps = {
  source: Source;
  flash?: boolean;
  /** in the side panel: tighter, and rows ruled apart */
  compact?: boolean;
  /** the words the answer quoted from this source, verbatim: marked with the highlighter */
  quoted?: string[];
  /** found for the question but not cited in the answer */
  uncited?: boolean;
};

export const SourceCard = forwardRef<HTMLLIElement, CardProps>(function SourceCard({ source: s, flash, compact, quoted, uncited }, ref) {
  const [open, setOpen] = useState(false);
  const terms = s.terms ?? [];
  const body = s.text ?? "";
  // The collapsed snippet opens on what the answer quoted, when it quoted something; otherwise on the best match.
  const firstQuote = quoted?.length ? quoteRanges(body, quoted)[0] : undefined;
  const skipped = firstQuote ? (firstQuote[0] > VISIBLE_CHARS / 2 ? sentenceStart(body, firstQuote[0]) : 0) : snippetStart(body, terms);
  const start = open ? 0 : skipped;
  const shown = start > 0 ? body.slice(start) : body;
  const marks = quoted?.length ? quoteRanges(shown, quoted) : [];
  // the text in order: plain stretches (with the question's terms underlined) and the quoted stretches (highlighted)
  const pieces: ReactNode[] = [];
  let at = 0;
  marks.forEach(([from, to], i) => {
    if (from > at) pieces.push(<Fragment key={`t${i}`}>{highlighted(shown.slice(at, from), terms)}</Fragment>);
    pieces.push(
      <mark key={`q${i}`} className="quote-mark">
        {shown.slice(from, to)}
      </mark>,
    );
    at = to;
  });
  if (at < shown.length) pieces.push(<Fragment key="rest">{highlighted(shown.slice(at), terms)}</Fragment>);
  const docId = s.turn_id.split(":")[0];

  // "Petikan penuh" only when there is more to show: the snippet is clamped, or it starts part-way in.
  const snipRef = useRef<HTMLParagraphElement>(null);
  const [clamped, setClamped] = useState(false);
  useEffect(() => {
    const el = snipRef.current;
    if (!el || open) return;
    const ro = new ResizeObserver(() => setClamped(el.scrollHeight > el.clientHeight + 1));
    ro.observe(el);
    return () => ro.disconnect();
  }, [open, body, compact]);
  const expandable = open || clamped || skipped > 0;

  return (
    <li
      ref={ref}
      id={`sumber-${s.n}`}
      tabIndex={-1}
      aria-label={`Sumber ${s.n}: ${s.speaker}`}
      className={cn("scroll-mt-24 list-none", compact ? "border-t border-line py-5 first:border-t-0 first:pt-1" : "rounded-lg py-6", flash && "flash")}
    >
      <div className="flex items-start gap-3">
        <span className={NUM}>{s.n}</span>
        <div className="min-w-0 flex-1">
          <p className="leading-snug font-medium [overflow-wrap:anywhere]">
            {s.profile_url ? (
              <a href={s.profile_url} target="_blank" rel="noopener" title="Profil rasmi di parlimen.gov.my" className="underline-offset-4 hover:underline">
                {s.speaker}
              </a>
            ) : (
              s.speaker
            )}
          </p>
          <p className="mt-1 text-[13px] leading-snug text-muted-foreground tabular">
            {[s.role, s.party ? `Parti semasa: ${s.party}` : null, s.date_display, s.section_heading ? headingCase(s.section_heading) : s.section].filter(Boolean).join(" · ")}
          </p>
          {s.unattributed || s.is_draft || s.ocr || uncited ? (
            <div className="mt-1.5 flex flex-wrap gap-1">
              {uncited ? <span className={TAG}>tidak dipetik dalam jawapan</span> : null}
              {s.unattributed ? <span className={TAG}>ahli tidak dinamakan</span> : null}
              {s.is_draft ? <span className={TAG}>draf: belum disemak</span> : null}
              {s.ocr ? <span className={TAG}>OCR</span> : null}
            </div>
          ) : null}

          <p
            ref={snipRef}
            id={`petikan-${s.n}`}
            className={cn(
              "mt-3 border-s-2 border-brand font-serif text-body whitespace-pre-line [overflow-wrap:anywhere]",
              compact ? "ps-3 text-[15px] leading-[1.6]" : "ps-4 text-[16px] leading-[1.6]",
              !open && "line-clamp-4",
            )}
          >
            {start > 0 ? "… " : null}
            {pieces}
          </p>

          <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-0 text-[13px]">
            <a
              href={s.pdf_url}
              target="_blank"
              rel="noopener"
              className="inline-flex min-h-9 items-center gap-1 text-brand underline-offset-4 hover:underline"
            >
              Lihat dalam Hansard, {(s.part ?? 0) > 0 ? "ucapan bermula hlm." : "hlm."} {s.page_label ?? "?"}{" "}
              <ArrowUpRight className="size-3.5" aria-hidden />
            </a>
            {/* The public site shows cited excerpts only: the full-transcript pages don't exist there. */}
            {PUBLIC_MODE ? null : (
              <Link href={`/sidang/${docId}#${encodeURIComponent(s.turn_id)}`} className={TEXT_BTN}>
                <BookOpen className="size-3.5" aria-hidden />
                <span className="sm:hidden">Sidang</span>
                <span className="hidden sm:inline">Buka dalam sidang</span>
              </Link>
            )}
            {expandable ? (
              <button
                type="button"
                onClick={() => setOpen(!open)}
                aria-expanded={open}
                aria-controls={`petikan-${s.n}`}
                className={cn(TEXT_BTN, "ms-auto")}
              >
                {open ? "Ringkaskan" : "Petikan penuh"}
              </button>
            ) : null}
          </div>
        </div>
      </div>
    </li>
  );
});
