"use client";

import { ArrowUpRight } from "lucide-react";
import { Fragment, type ReactElement, type ReactNode, useState } from "react";

import { HoverCard, HoverCardContent, HoverCardTrigger } from "@/components/ui/hover-card";
import type { Source } from "@/lib/api";
import { cn } from "@/lib/utils";

// A quoted passage of at least this many words becomes a blockquote with the cited speaker in its <cite>.
const QUOTE_MIN_WORDS = 6;
// groups: 1 bold, 2-4 verbatim quote (3 text, 4 trailing citations), 5-6 citation, 7-8 *italic* (8 text)
const INLINE =
  /(\*\*[^*\n]+\*\*)|(["“]([^"“”\n]{12,700}?)["”][ \t]*((?:\[\d{1,2}\])*)[.,;]?)|(\[(\d{1,2})\])|(\*(?![\s*])([^*\n]+?)(?<![\s*])\*)/g;

const norm = (s: string) => s.replace(/\s+/g, " ").trim();
const flat = (s: string) => s.replace(/[‘’]/g, "'").replace(/\s+/g, " ").trim();

/** Same rule as unverified_quotes() in generate/answer.py ("..." splits a quote into parts), but against ONE source. */
export const quoteInSource = (quote: string, src: Source) => {
  const hay = flat(src.text ?? "");
  return quote
    .split(/\s*(?:\.\.\.|…)\s*/)
    .map((p) => flat(p).replace(/^[ .,]+|[ .,]+$/g, ""))
    .filter(Boolean)
    .every((p) => hay.includes(p));
};

/** The single source that contains the quote, or nothing when none or more than one does (two speakers, no guess). */
const onlySource = (quote: string, sources: Source[]) => {
  const hits = sources.filter((s) => quoteInSource(quote, s));
  return hits.length > 0 && hits.every((s) => s.speaker_id === hits[0].speaker_id && s.speaker === hits[0].speaker) ? hits[0] : undefined;
};

export const citedSources = (tail: string, sources: Source[]) =>
  [...tail.matchAll(/\[(\d{1,2})\]/g)].map((c) => sources[Number(c[1]) - 1]).filter(Boolean);

/** The long quotes the answer shows as blockquotes: [text, trailing citations]. Mirrors the quote branch of INLINE. */
export const longQuotes = (text: string): [string, string][] =>
  [...text.matchAll(/["“]([^"“”\n]{12,700}?)["”][ \t]*((?:\[\d{1,2}\])*)/g)]
    .map((m): [string, string] => [m[1].trim(), m[2] ?? ""])
    .filter(([q]) => q.split(/\s+/).length >= QUOTE_MIN_WORDS);

/** A citation number with its source previewed on hover or focus. */
function SourcePreview({ src, chip }: { src: Source; chip: ReactElement }) {
  const [open, setOpen] = useState(false);
  return (
    <HoverCard open={open} onOpenChange={setOpen}>
      {/* clicking goes to the full source in the other tab, so the preview must not stay behind */}
      <HoverCardTrigger render={chip} onClick={() => setOpen(false)} />
      <HoverCardContent>
        <p className="text-[13px] leading-snug font-medium text-foreground">{src.speaker}</p>
        <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground tabular">
          {src.date_display}
          {src.page_label ? ` · hlm. ${src.page_label}` : ""}
        </p>
        <p className="mt-2 line-clamp-4 font-serif text-[14px] leading-[1.55] text-foreground [overflow-wrap:anywhere]">{src.text}</p>
        <p className="mt-2 text-[12px] text-muted-foreground">Klik nombor untuk petikan penuh.</p>
      </HoverCardContent>
    </HoverCard>
  );
}

type Props = {
  text: string;
  sources: Source[];
  missing?: number[];
  unverified?: string[];
  streaming?: boolean;
  onCite: (n: number) => void;
};

type Block = { kind: "p" | "li"; nodes: ReactNode[] } | { kind: "quote"; node: ReactNode } | { kind: "h"; text: string };

/**
 * The model's answer as React nodes (never innerHTML): paragraphs, bullets, **bold**, [n] citation buttons,
 * and verbatim quotes as blockquotes: serif, a 2px accent bar, and under each one who said it, when, and a link
 * to the PDF. A quote the verbatim check couldn't find word for word gets a dashed grey bar and a "tidak disahkan" label.
 */
export function Answer({ text, sources, missing = [], unverified = [], streaming, onCite }: Props) {
  const shaky = new Set(unverified.map(norm));
  const bad = new Set(missing);

  const cite = (n: number, key: string) => {
    const ok = n >= 1 && n <= sources.length && !bad.has(n);
    const chip = (
      <button
        key={key}
        type="button"
        onClick={() => ok && onCite(n)}
        title={ok ? undefined : "Rujukan tanpa sumber"}
        aria-label={ok ? `Sumber ${n}: ${sources[n - 1].speaker}` : `Rujukan ${n} tanpa sumber`}
        aria-disabled={ok ? undefined : true}
        className={cn(
          "relative ms-1 inline-flex h-5 min-w-6 -translate-y-px items-center justify-center rounded-md border border-line bg-surface px-1 align-middle font-sans text-[11px] font-medium tabular before:absolute before:-inset-x-1.5 before:-inset-y-1 before:content-['']",
          // a citation is one of the three places the accent is allowed
          ok ? "text-brand" : "cursor-default text-muted-foreground line-through",
        )}
      >
        {n}
      </button>
    );
    if (!ok) return chip;
    // Hovering (or focusing) a citation previews its source: who, when, and the start of what was said.
    // Touch has no hover: a tap goes to the full source, as before.
    return <SourcePreview key={key} src={sources[n - 1]} chip={chip} />;
  };

  const citesIn = (s: string, key: string) =>
    [...s.matchAll(/\[(\d{1,2})\]/g)].map((m, i) => cite(Number(m[1]), `${key}c${i}`));

  const withCites = (s: string, key: string): ReactNode[] =>
    s.split(/(\[\d{1,2}\])/).map((part, i) => {
      const c = /^\[(\d{1,2})\]$/.exec(part);
      return c ? cite(Number(c[1]), `${key}e${i}`) : part;
    });

  const blocks: Block[] = [];
  text.split("\n").forEach((line, li) => {
    const heading = /^\s*\*\*([^*\n]+)\*\*:?\s*$/.exec(line);
    if (heading) {
      blocks.push({ kind: "h", text: heading[1].trim() });
      return;
    }
    const bullet = /^\s*[*-]\s+/.exec(line);
    const body = bullet ? line.slice(bullet[0].length) : line;
    let current: ReactNode[] = [];
    const flush = () => {
      if (current.length) blocks.push({ kind: bullet ? "li" : "p", nodes: current });
      current = [];
    };
    let last = 0;
    for (const m of body.matchAll(INLINE)) {
      const key = `${li}-${m.index}`;
      if (m.index > last) current.push(body.slice(last, m.index));
      last = m.index + m[0].length;
      if (m[1]) current.push(<strong key={key} className="font-medium text-foreground">{m[1].slice(2, -2)}</strong>);
      else if (m[6]) current.push(cite(Number(m[6]), key));
      else if (m[8]) current.push(<em key={key}>{withCites(m[8], key)}</em>);
      else if (m[3]) {
        const quote = m[3].trim();
        if (quote.split(/\s+/).length < QUOTE_MIN_WORDS) {
          current.push(
            shaky.has(norm(quote)) ? (
              <span
                key={`${key}q`}
                title="tidak disahkan: bukan petikan kata demi kata"
                className="underline decoration-muted-foreground decoration-dashed underline-offset-4"
              >
                “{quote}”<span className="sr-only"> (tidak disahkan)</span>
              </span>
            ) : (
              `“${quote}”`
            ),
            ...citesIn(m[4] ?? "", key),
          );
          continue;
        }
        const tail = m[4] ?? "";
        const citedTo = citedSources(tail, sources);
        // The speaker and link under a quote: the cited source that contains it; or, when the model put no number
        // after the quote, the one source whose text contains it word for word (never a guess: no match, no name).
        const src =
          citedTo.find((s) => quoteInSource(quote, s)) ?? citedTo[0] ?? (streaming ? undefined : onlySource(quote, sources));
        // Only judged once the answer is complete: mid-stream the citation after a quote may not have arrived yet.
        const wrongSource = !streaming && citedTo.length > 0 && !citedTo.some((s) => quoteInSource(quote, s));
        const failedCheck = shaky.has(norm(quote));
        const isShaky = failedCheck || wrongSource;
        const quoteNode = (
          <blockquote
            key={key}
            className={cn(
              "border-s-2 ps-4 font-serif text-[17px] leading-[1.6] text-foreground [overflow-wrap:anywhere]",
              bullet ? "mt-3 mb-3" : "my-5",
              isShaky ? "border-dashed border-muted-foreground" : "border-brand",
            )}
          >
            {quote}
            {src || tail ? (
              <cite className="mt-2 block font-sans text-[13px] leading-relaxed text-muted-foreground not-italic">
                {src ? (
                  <span className="tabular">
                    {src.speaker} · {src.date_display}
                  </span>
                ) : null}
                {citesIn(tail, key)}
                {src ? (
                  <a
                    href={src.pdf_url}
                    target="_blank"
                    rel="noopener"
                    className="mt-0.5 flex w-fit items-center gap-1 text-brand underline-offset-4 hover:underline"
                  >
                    Lihat dalam Hansard, {(src.part ?? 0) > 0 ? "ucapan bermula hlm." : "hlm."} {src.page_label ?? "?"}
                    <ArrowUpRight className="size-3.5" aria-hidden />
                  </a>
                ) : null}
              </cite>
            ) : null}
            {isShaky ? (
              <span className="mt-2 block w-fit rounded-md border border-line bg-surface px-2 py-0.5 font-sans text-[12px] text-foreground">
                {wrongSource && !failedCheck
                  ? "tidak disahkan: tiada dalam sumber yang dirujuk"
                  : "tidak disahkan: bukan petikan kata demi kata"}
              </span>
            ) : null}
          </blockquote>
        );
        // In a bullet the quote stays inside its <li>, under the MP the bullet names. (A <p> can't hold a blockquote.)
        if (bullet) current.push(quoteNode);
        else {
          flush();
          blocks.push({ kind: "quote", node: quoteNode });
        }
      }
    }
    if (last < body.length) current.push(body.slice(last));
    flush();
  });

  // bullets that follow each other form one list
  const out: ReactNode[] = [];
  for (let i = 0; i < blocks.length; i++) {
    const b = blocks[i];
    if (b.kind === "quote") out.push(b.node);
    else if (b.kind === "h")
      out.push(
        <h3 key={`h${i}`} className="pt-2 text-[16px] font-medium text-foreground">
          {b.text}
        </h3>,
      );
    else if (b.kind === "p") out.push(<p key={`p${i}`}>{b.nodes}</p>);
    else {
      const items: ReactNode[] = [];
      while (i < blocks.length && blocks[i].kind === "li") {
        items.push(<li key={`li${i}`}>{(blocks[i] as { nodes: ReactNode[] }).nodes}</li>);
        i++;
      }
      i--;
      out.push(
        <ul key={`ul${i}`} className="list-disc space-y-4 ps-5 marker:text-muted-foreground">
          {items}
        </ul>,
      );
    }
  }

  return (
    <div
      className={cn(
        "max-w-[65ch] space-y-4 text-[16px] leading-[1.7] text-body text-pretty",
        streaming &&
          "[&>*:last-child]:after:ml-0.5 [&>*:last-child]:after:inline-block [&>*:last-child]:after:h-[1.05em] [&>*:last-child]:after:w-[7px] [&>*:last-child]:after:translate-y-[3px] [&>*:last-child]:after:animate-pulse [&>*:last-child]:after:rounded-sm [&>*:last-child]:after:bg-foreground [&>*:last-child]:after:content-['']",
      )}
    >
      {out.map((node, i) => (
        <Fragment key={i}>{node}</Fragment>
      ))}
    </div>
  );
}
