"use client";

import { ArrowUpRight, BookOpen } from "lucide-react";
import Link from "next/link";
import { forwardRef, useState, type ReactNode } from "react";

import { SpeakerAvatar } from "@/components/speaker-avatar";
import { Badge } from "@/components/ui/badge";
import type { Source } from "@/lib/api";
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

/** The text with the question's terms wrapped in <mark>; the words themselves are never changed. */
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
      <mark key={i} className="rounded-[3px] bg-primary/20 px-px text-foreground">
        {m[0]}
      </mark>,
    );
    last = i + m[0].length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

/** One numbered source: who, when, where in the sitting, the verbatim text, and the exact PDF page. */
export const SourceCard = forwardRef<HTMLLIElement, { source: Source; flash?: boolean }>(function SourceCard(
  { source: s, flash },
  ref,
) {
  const [open, setOpen] = useState(false);
  const terms = s.terms ?? [];
  const body = s.text ?? "";
  const start = open ? 0 : snippetStart(body, terms);
  const named = Boolean(s.speaker_id) && !s.unattributed;
  const docId = s.turn_id.split(":")[0];
  const avatar = (
    <SpeakerAvatar speaker={s.speaker} initials={s.initials} photoUrl={s.photo_url} named={named} size="lg" />
  );
  return (
    <li
      ref={ref}
      id={`sumber-${s.n}`}
      className={cn(
        "scroll-mt-24 list-none rounded-2xl bg-card p-4 shadow-[0_0_0_1px_var(--border-subtle),0_1px_2px_rgb(0_0_0/0.04)] transition-shadow hover:shadow-[0_0_0_1px_var(--border-default),0_10px_24px_-14px_rgb(0_0_0/0.25)] sm:p-5",
        flash && "flash",
      )}
    >
      <header className="flex items-start gap-3">
        {s.profile_url ? (
          <a href={s.profile_url} target="_blank" rel="noopener" title="Profil rasmi di parlimen.gov.my" className="shrink-0 rounded-full">
            {avatar}
          </a>
        ) : (
          avatar
        )}
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="inline-grid h-5 min-w-5 place-items-center rounded-md bg-muted px-1 text-[11px] font-semibold tabular text-muted-foreground">
              {s.n}
            </span>
            <span className="font-semibold leading-snug tracking-[-0.005em]">{s.speaker}</span>
            {s.unattributed ? <Badge variant="secondary">ahli tidak dinamakan</Badge> : null}
            {s.is_draft ? <Badge className="bg-warning text-warning-foreground">draf: belum disemak</Badge> : null}
            {s.ocr ? <Badge className="bg-info text-info-foreground">OCR</Badge> : null}
          </div>
          <p className="mt-1 text-[12.5px] leading-snug text-subtle tabular">
            {[s.role, s.party ? `Parti semasa: ${s.party}` : null, s.date_display, s.section_heading ? headingCase(s.section_heading) : s.section].filter(Boolean).join(" · ")}
          </p>
        </div>
      </header>

      <p
        className={cn(
          "mt-3 border-s-2 border-strong-border ps-3 text-[14px] leading-relaxed text-muted-foreground whitespace-pre-line",
          !open && "line-clamp-4",
        )}
      >
        {start > 0 ? "… " : null}
        {highlighted(start > 0 ? body.slice(start) : body, terms)}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 border-t pt-3 text-[13px]">
        <a
          href={s.pdf_url}
          target="_blank"
          rel="noopener"
          className="inline-flex min-h-8 items-center gap-1 font-medium text-link hover:underline underline-offset-2"
        >
          Lihat dalam Hansard, hlm. {s.page_label ?? "?"} <ArrowUpRight className="size-3.5" />
        </a>
        <Link
          href={`/sidang/${docId}#${encodeURIComponent(s.turn_id)}`}
          className="inline-flex min-h-8 items-center gap-1 text-muted-foreground hover:text-foreground"
        >
          <BookOpen className="size-3.5" /> Buka dalam sidang
        </Link>
        <button type="button" onClick={() => setOpen(!open)} className="ms-auto min-h-8 text-muted-foreground hover:text-foreground">
          {open ? "Ringkaskan" : "Petikan penuh"}
        </button>
      </div>
    </li>
  );
});
