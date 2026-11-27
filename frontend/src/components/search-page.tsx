"use client";

import { ArrowRight } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { FilterChips } from "@/components/filter-chips";
import { LandingSheet } from "@/components/landing-sheet";
import { Results } from "@/components/results";
import { apiUrl, type Filters, type Status } from "@/lib/api";
import { coverage, isPartial, STARTERS } from "@/lib/copy";
import { cn } from "@/lib/utils";

/**
 * Search-first page: the landing page pairs the composer with a sheet of Hansard showing one highlighted line;
 * on a results page the question becomes the heading and the composer pins to the bottom for the next question.
 * The question and filters live in the URL (?q=&speaker=&from=&to=), so a search is a shareable link and there
 * is no chat history (spec: single question, no saved threads).
 */
export function SearchPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const filters: Filters = { speakerId: params.get("speaker"), party: params.get("party"), dateFrom: params.get("from"), dateTo: params.get("to") };
  const hasFilters = Boolean(filters.speakerId || filters.party || filters.dateFrom || filters.dateTo);
  const searching = q.length >= 2;

  // Starting a search from the landing page replaces the whole view: move focus to the new heading (the question)
  // so keyboard and screen-reader users land on the result instead of on <body>.
  const h1Ref = useRef<HTMLHeadingElement>(null);
  const wasSearching = useRef(searching);
  useEffect(() => {
    if (searching && !wasSearching.current) h1Ref.current?.focus({ preventScroll: true });
    wasSearching.current = searching;
  }, [searching]);

  // The composer starts empty for the next question; it clears whenever the URL's question changes.
  const [draft, setDraft] = useState("");
  const [shownQ, setShownQ] = useState(q);
  if (shownQ !== q) {
    setShownQ(q);
    setDraft("");
  }
  // "Try again" re-runs the same question: the URL doesn't change, so a counter is what restarts the search.
  const [attempt, setAttempt] = useState(0);

  const [status, setStatus] = useState<Status | null>(null);
  useEffect(() => {
    fetch(apiUrl("/api/status"))
      .then((r) => r.json())
      .then(setStatus)
      .catch(() => setStatus(null));
  }, []);

  const go = (next: { q?: string; filters?: Filters }) => {
    const f = next.filters ?? filters;
    const sp = new URLSearchParams();
    const query = (next.q ?? q).trim();
    if (query) sp.set("q", query);
    if (f.speakerId) sp.set("speaker", f.speakerId);
    if (f.party) sp.set("party", f.party);
    if (f.dateFrom) sp.set("from", f.dateFrom);
    if (f.dateTo) sp.set("to", f.dateTo);
    const qs = sp.toString();
    router.push(qs ? `${pathname}?${qs}` : pathname, { scroll: false });
  };

  const submit = () => {
    const next = draft.trim();
    if (next.length < 2) return;
    if (next === q) {
      setAttempt((a) => a + 1);
      setDraft("");
    } else go({ q: next });
  };

  const dbDown = status?.database === "unreachable";
  const DB_DOWN = "Pangkalan data carian tidak dapat dihubungi buat masa ini. Sila cuba lagi sebentar nanti.";

  // One composer: the question on top, a toolbar row under it (filters once a search has run, send on the right).
  const composer = (
    <form
      role="search"
      onSubmit={(e) => {
        e.preventDefault();
        submit();
      }}
      className="searchbar elev rounded-xl border border-line bg-surface"
    >
      <label htmlFor="q" className="sr-only">
        Soalan
      </label>
      <textarea
        id="q"
        rows={searching ? 1 : 2}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          // one question, one line of thought: Enter sends it
          // (not while an input method is still composing: there Enter only confirms the word being typed)
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing && e.keyCode !== 229) {
            e.preventDefault();
            submit();
          }
        }}
        maxLength={500}
        placeholder="Tanya tentang perbahasan Dewan Rakyat…"
        // grows with what is typed (up to a point), so a long or prefilled question is never edited blind;
        // rows is the fallback where field-sizing is not supported
        className={cn(
          "block field-sizing-content max-h-40 w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 text-[16px] leading-normal outline-none placeholder:overflow-hidden placeholder:text-ellipsis placeholder:whitespace-nowrap placeholder:text-muted-foreground",
          !searching && "min-h-[3.875rem]",
        )}
        autoComplete="off"
        enterKeyHint="search"
      />
      <div className="flex items-center gap-2 py-2 ps-4 pe-2">
        <div className="min-w-0 flex-1">
          {searching ? <FilterChips value={filters} onChange={(f) => go({ filters: f })} status={status} /> : null}
        </div>
        {/* the one round thing in the app, and one of the three places the accent is allowed */}
        <button
          type="submit"
          disabled={draft.trim().length < 2}
          aria-label="Cari"
          className="press grid size-9 shrink-0 place-items-center rounded-full bg-brand-fill text-on-brand disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ArrowRight className="size-[18px]" aria-hidden />
        </button>
      </div>
    </form>
  );

  if (!searching) {
    return (
      // a container, so the two columns depend on the room the page really has (the rail takes some on desktop)
      <div className="@container flex flex-1 flex-col justify-center overflow-x-clip">
        <div className="mx-auto flex w-full max-w-[1104px] flex-col gap-10 px-5 py-10 sm:px-8">
          <div className="grid grid-cols-[minmax(0,1fr)] items-center gap-10 @4xl:grid-cols-[minmax(0,0.48fr)_minmax(0,0.52fr)] @4xl:gap-16">
            <div className="flex flex-col">
              <p className="text-[12px] tracking-[0.08em] text-muted-foreground uppercase">Penyata Rasmi Dewan Rakyat · Parlimen ke-15</p>
              <h1 className="mt-5 font-serif text-[clamp(38px,7cqi,60px)] leading-[1.07] font-normal tracking-[-0.02em] text-balance">
                Tanya apa sahaja tentang Dewan Rakyat.
              </h1>
              <p className="mt-5 mb-7 text-[17px] leading-7 text-muted-foreground @4xl:text-[18px]">Pustakawan, bukan pengulas politik.</p>
              {composer}
              <section aria-label="Contoh soalan" className="mt-8">
                <h2 className="mb-1 text-[12px] font-normal tracking-[0.08em] text-muted-foreground uppercase">Cuba tanya</h2>
                {/* quiet rows, not cards: the hairline between them is what makes this read as a list */}
                <ul>
                  {STARTERS.map((s) => (
                    <li key={s} className="border-b border-line last:border-b-0">
                      <button
                        type="button"
                        onClick={() => go({ q: s })}
                        className="-mx-2 block min-h-11 w-[calc(100%+1rem)] rounded-lg px-2 py-2.5 text-left text-[15px] leading-snug text-body transition-colors duration-150 hover:bg-hover"
                      >
                        {s}
                      </button>
                    </li>
                  ))}
                </ul>
              </section>
            </div>
            <LandingSheet />
          </div>
          {status ? (
            <p role={dbDown ? "status" : undefined} className="border-t border-line pt-5 text-[13px] leading-5 text-muted-foreground tabular text-balance @4xl:text-center">
              {dbDown ? (
                DB_DOWN
              ) : (
                <>
                  {coverage(status)} · {status.chunks.toLocaleString("en-US")} petikan diindeks
                  {isPartial(status) ? ". Pustakawan masih membaca." : "."}
                </>
              )}
            </p>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    // the same frame as the header and the landing page, so the logo, the question and the answer share one edge
    <div className="mx-auto flex w-full max-w-[1104px] flex-1 flex-col px-5 sm:px-8">
      {/* the question is the page heading, set like the landing page's headline */}
      <header className="pt-6 pb-6 sm:pt-10 lg:mb-8 lg:border-b lg:border-line lg:pb-8">
        <p className="text-[12px] tracking-[0.08em] text-muted-foreground uppercase">Soalan</p>
        <h1
          ref={h1Ref}
          tabIndex={-1}
          className={cn(
            "mt-3 max-w-[26ch] font-serif leading-[1.12] font-normal tracking-[-0.02em] text-balance [overflow-wrap:anywhere]",
            // a very long question steps down, so it never fills the screen
            q.length > 110 ? "max-w-[44ch] text-[clamp(22px,3vw,28px)] leading-[1.25]" : "text-[clamp(28px,4.4vw,44px)]",
          )}
        >
          {q}
        </h1>
      </header>
      {dbDown ? (
        <p role="status" className="mb-6 text-[13px] text-muted-foreground">
          {DB_DOWN}
        </p>
      ) : null}
      <Results
        key={`${q}|${filters.speakerId ?? ""}|${filters.party ?? ""}|${filters.dateFrom ?? ""}|${filters.dateTo ?? ""}|${attempt}`}
        question={q}
        filters={filters}
        status={status}
        hasFilters={hasFilters}
        onRetry={() => setAttempt((a) => a + 1)}
        onClearFilters={() => go({ filters: { speakerId: null, party: null, dateFrom: null, dateTo: null } })}
        onEdit={() => {
          setDraft(q);
          requestAnimationFrame(() => {
            const el = document.getElementById("q") as HTMLTextAreaElement | null;
            el?.focus();
            el?.select();
          });
        }}
        // the composer for the next question stays within reach at the bottom of the screen, under the answer
        composer={<div className="sticky bottom-0 z-20 bg-background pt-2 pb-4">{composer}</div>}
      />
    </div>
  );
}
