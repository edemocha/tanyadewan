"use client";

import { ArrowRight, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { FilterChips } from "@/components/filter-chips";
import { LogoMark } from "@/components/logo-mark";
import { Results } from "@/components/results";
import { apiUrl, type Filters, type Status } from "@/lib/api";
import { coverage, isPartial, STARTERS } from "@/lib/copy";
import { cn } from "@/lib/utils";

/**
 * Search-first page, laid out like an answer engine: a centred title and one composer box on the landing page;
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
      className="searchbar skeu skeu-well rounded-lg bg-surface"
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
          "block field-sizing-content max-h-40 w-full resize-none overflow-y-auto bg-transparent px-4 pt-3.5 text-[16px] leading-normal outline-none placeholder:text-muted-foreground",
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
          className="skeu skeu-raised skeu-send grid size-9 shrink-0 place-items-center rounded-full bg-brand-fill text-on-brand disabled:cursor-not-allowed disabled:opacity-40"
        >
          <ArrowRight className="size-[18px]" aria-hidden />
        </button>
      </div>
    </form>
  );

  if (!searching) {
    return (
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col justify-center px-5 py-10 sm:px-6">
        <LogoMark className="mx-auto mb-5 size-12" />
        <h1 className="text-center font-heading text-[clamp(26px,4.5vw,34px)] leading-[1.15] font-medium tracking-[-0.02em] text-balance">
          Tanya apa sahaja tentang Dewan Rakyat.
        </h1>
        <p className="mt-3 mb-8 text-center text-[15px] text-muted-foreground">Pustakawan, bukan pengulas politik.</p>
        {composer}
        {status ? (
          <p role={dbDown ? "status" : undefined} className="mt-3 text-center text-[12px] text-muted-foreground tabular text-pretty">
            {dbDown ? (
              DB_DOWN
            ) : (
              <>
                Buat masa ini: {coverage(status)}
                {isPartial(status) ? ". Pustakawan masih membaca." : "."}
              </>
            )}
          </p>
        ) : null}
        <section aria-label="Contoh soalan" className="mt-12">
          <p className="mb-2 text-[12px] tracking-[0.08em] text-muted-foreground uppercase">Cuba tanya</p>
          {/* Gradient cards, as on the answer engine this layout follows: the first one bright, the rest quiet.
              Raised and pressable (.skeu-raised); gradients and shading are mixed from the palette in globals.css. */}
          <ul className="grid gap-3 sm:grid-cols-2">
            {STARTERS.map((s, i) => (
              <li key={s}>
                <button
                  type="button"
                  onClick={() => go({ q: s })}
                  className={cn(
                    "skeu skeu-raised flex h-full w-full flex-col gap-2 rounded-lg p-4 text-left",
                    i === 0 ? "card-bright" : "card-quiet",
                  )}
                >
                  <Search className="size-4" aria-hidden />
                  <span className="text-[15px] leading-snug font-medium">{s}</span>
                </button>
              </li>
            ))}
          </ul>
        </section>
      </div>
    );
  }

  return (
    <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col px-5 sm:px-6">
      {/* the question is the page heading */}
      <h1 ref={h1Ref} tabIndex={-1} className="pt-6 pb-6 font-heading text-[clamp(24px,4vw,30px)] leading-[1.2] font-medium tracking-[-0.02em] text-balance sm:pt-10">
        {q}
      </h1>
      <div className="flex-1 pb-10">
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
        />
      </div>
      {/* the composer for the next question stays within reach at the bottom of the screen */}
      <div className={cn("sticky bottom-0 z-20 -mx-5 bg-background px-5 pt-2 pb-4 sm:-mx-6 sm:px-6")}>{composer}</div>
    </div>
  );
}
