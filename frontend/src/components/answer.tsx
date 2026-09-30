"use client";

import { Fragment, type ReactNode } from "react";

import { SpeakerAvatar } from "@/components/speaker-avatar";
import type { Source } from "@/lib/api";
import { cn } from "@/lib/utils";

// A quoted passage of at least this many words becomes a blockquote with the cited speaker in its <cite>.
const QUOTE_MIN_WORDS = 6;
// groups: 1 bold, 2-4 verbatim quote (3 text, 4 trailing citations), 5-6 citation, 7-8 *italic* (8 text)
const INLINE =
  /(\*\*[^*\n]+\*\*)|(["“]([^"“”\n]{12,700}?)["”][ \t]*((?:\[\d{1,2}\])*)[.,;]?)|(\[(\d{1,2})\])|(\*(?![\s*])([^*\n]+?)(?<![\s*])\*)/g;

const norm = (s: string) => s.replace(/\s+/g, " ").trim();

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
 * and verbatim quotes as Blockquotes (the Astryx structure: 2px inline-start rule, bare <cite> below).
 * A quote the verbatim check couldn't find word for word gets a dashed rule and a "tidak disahkan" label.
 */
export function Answer({ text, sources, missing = [], unverified = [], streaming, onCite }: Props) {
  const shaky = new Set(unverified.map(norm));
  const bad = new Set(missing);

  const cite = (n: number, key: string) => {
    const ok = n >= 1 && n <= sources.length && !bad.has(n);
    return (
      <button
        key={key}
        type="button"
        onClick={() => ok && onCite(n)}
        title={ok ? `Sumber ${n}` : "Rujukan tanpa sumber"}
        className={cn(
          "relative mx-0.5 inline-flex h-5 min-w-6 -translate-y-px items-center justify-center rounded-md px-1 align-middle text-[11px] font-semibold tabular transition-colors before:absolute before:-inset-y-1 before:inset-x-0 before:content-['']",
          ok ? "bg-primary text-primary-foreground hover:bg-primary/85" : "text-destructive line-through ring-1 ring-error-border ring-inset",
        )}
      >
        {n}
      </button>
    );
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
      if (m[1]) current.push(<strong key={key} className="font-semibold">{m[1].slice(2, -2)}</strong>);
      else if (m[6]) current.push(cite(Number(m[6]), key));
      else if (m[8]) current.push(<em key={key}>{withCites(m[8], key)}</em>);
      else if (m[3]) {
        const quote = m[3].trim();
        if (quote.split(/\s+/).length < QUOTE_MIN_WORDS) {
          current.push(`“${quote}”`, ...citesIn(m[4] ?? "", key));
          continue;
        }
        flush();
        const first = /\[(\d{1,2})\]/.exec(m[4] ?? "")?.[1];
        const src = first ? sources[Number(first) - 1] : undefined;
        const isShaky = shaky.has(norm(quote));
        blocks.push({
          kind: "quote",
          node: (
            <blockquote
              key={key}
              className={cn(
                "my-4 border-s-2 ps-4 text-[15px] leading-relaxed text-muted-foreground [overflow-wrap:anywhere]",
                isShaky ? "border-dashed border-error-border" : "border-strong-border",
              )}
            >
              {quote}
              <cite className="mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-[12.5px] leading-snug not-italic text-subtle">
                {src ? (
                  <>
                    <SpeakerAvatar
                      size="sm"
                      speaker={src.speaker}
                      initials={src.initials}
                      photoUrl={src.photo_url}
                      named={Boolean(src.speaker_id) && !src.unattributed}
                    />
                    <span>
                      {src.speaker} · {src.date_display}
                    </span>
                  </>
                ) : null}
                {citesIn(m[4] ?? "", key)}
                {isShaky ? (
                  <span className="rounded-full bg-error px-2 text-[11px] text-error-foreground">
                    tidak disahkan: bukan petikan kata demi kata
                  </span>
                ) : null}
              </cite>
            </blockquote>
          ),
        });
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
        <h3 key={`h${i}`} className="pt-2 text-[15px] font-semibold tracking-[-0.005em]">
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
        <ul key={`ul${i}`} className="list-disc space-y-1.5 ps-5 marker:text-subtle">
          {items}
        </ul>,
      );
    }
  }

  return (
    <div
      className={cn(
        "max-w-[68ch] space-y-3 text-[16px] leading-[1.75] text-pretty",
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
