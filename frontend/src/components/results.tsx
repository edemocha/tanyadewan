"use client";

import { Check as CheckIcon, ChevronDown, Copy } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Answer, citedSources, longQuotes, quoteInSource } from "@/components/answer";
import { SourceCard } from "@/components/source-card";
import { SourceDates } from "@/components/source-dates";
import { Skeleton } from "@/components/ui/skeleton";
import { ask, type Check, type Filters, type Source, type Status } from "@/lib/api";
import { coverage, isPartial, LOADING } from "@/lib/copy";
import { cn } from "@/lib/utils";

type Phase = "searching" | "answering" | "done" | "error";
type Tab = "jawapan" | "sumber";

// A hosted backend can be slow to wake (it loads about 1.2 GB of models on a cold start): say so after this long,
// and give up rather than show a spinner forever.
const SLOW_AFTER_MS = 20_000;
const GIVE_UP_AFTER_MS = 120_000;
// How long a source stays outlined after its citation number is tapped (matches .flash in globals.css).
const FLASH_MS = 2600;

const LABEL = "text-[12px] tracking-[0.08em] text-muted-foreground uppercase";
// Neutral buttons: the accent is reserved for the send button and citations.
const BTN = "press inline-flex h-10 items-center rounded-lg px-4 text-[13px] font-medium";
const BTN_SOLID = `${BTN} bg-primary text-primary-foreground`;
const BTN_QUIET = `${BTN} border border-line bg-surface text-foreground`;
const TEXT_BTN = "inline-flex min-h-9 items-center gap-1.5 rounded-lg px-2 text-[13px] text-muted-foreground transition-colors hover:bg-hover hover:text-foreground";

type Props = {
  question: string;
  filters: Filters;
  status: Status | null;
  hasFilters: boolean;
  onRetry: () => void;
  onClearFilters: () => void;
  /** put the current question back in the composer so it can be reworded */
  onEdit: () => void;
};

/**
 * One search: streams /api/ask and shows it as two tabs, the answer (with a strip of its sources on top and the
 * "based on N sittings" line under it) and the full source list.
 * The parent keys this component by question + filters + attempt, so every new search starts from a clean state.
 */
export function Results({ question, filters, status, hasFilters, onRetry, onClearFilters, onEdit }: Props) {
  const [phase, setPhase] = useState<Phase>("searching");
  const [sources, setSources] = useState<Source[]>([]);
  const [answer, setAnswer] = useState("");
  const [check, setCheck] = useState<Check | null>(null);
  const [error, setError] = useState("");
  const [meta, setMeta] = useState("");
  const [loadingLine, setLoadingLine] = useState(0);
  const [slow, setSlow] = useState(false);
  const [flashN, setFlashN] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const [tab, setTab] = useState<Tab>("jawapan");
  // If the reader opened the source list while the answer was still streaming, leave the rows where they are:
  // folding the uncited ones at the end would pull the row they are reading out from under them.
  const [sawListEarly, setSawListEarly] = useState(false);
  const cardRefs = useRef(new Map<number, HTMLLIElement>());
  const flashTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    const ctl = new AbortController();
    let engine = "";
    let text = "";
    let sawDone = false;
    const slowTimer = setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    const giveUpTimer = setTimeout(() => {
      ctl.abort();
      setError("pelayan tidak menjawab dalam 2 minit");
      setPhase("error");
    }, GIVE_UP_AFTER_MS);
    (async () => {
      try {
        for await (const ev of ask(question, filters, ctl.signal)) {
          if (ev.event === "done") sawDone = true;
          if (ev.event === "sources") setSources(ev.data);
          else if (ev.event === "engine") engine = ev.data;
          else if (ev.event === "token") {
            text += ev.data;
            setAnswer(text);
            setPhase("answering");
          } else if (ev.event === "check") setCheck(ev.data);
          else if (ev.event === "error") setError(ev.data);
          else if (ev.event === "done" && ev.data.retrieve_ms !== undefined) {
            const secs = ((ev.data.generate_ms ?? 0) / 1000).toFixed(1);
            setMeta(`${engine || "tiada model"} · carian ${ev.data.retrieve_ms} ms · jawapan ${secs} s`);
          }
        }
        if (!sawDone) {
          setError("sambungan terputus sebelum jawapan selesai");
          setPhase("error");
        } else {
          setPhase("done");
        }
      } catch (e) {
        if (ctl.signal.aborted) return;
        setError(e instanceof Error ? e.message : String(e));
        setPhase("error");
      } finally {
        clearTimeout(slowTimer);
        clearTimeout(giveUpTimer);
      }
    })();
    return () => {
      clearTimeout(slowTimer);
      clearTimeout(giveUpTimer);
      ctl.abort();
    };
    // filters is rebuilt from the URL on every render; the parent's key already covers its values
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [question]);

  useEffect(() => {
    if (phase !== "searching") return;
    const t = setInterval(() => setLoadingLine((i) => i + 1), 1800);
    return () => clearInterval(t);
  }, [phase]);

  useEffect(
    () => () => {
      if (flashTimer.current) clearTimeout(flashTimer.current);
    },
    [],
  );

  // A citation number (or a tile in the source strip) opens the Sumber tab at that source. Both panels stay
  // mounted, so the row exists already; it only has to become visible before it can be scrolled to.
  const onCite = (n: number) => {
    if (phase !== "done") setSawListEarly(true);
    setTab("sumber");
    if (flashTimer.current) clearTimeout(flashTimer.current);
    setFlashN(null);
    requestAnimationFrame(() =>
      requestAnimationFrame(() => {
        const el = cardRefs.current.get(n);
        if (!el) return;
        // a source the answer didn't cite sits in the folded list: open it first
        const fold = el.closest("details");
        if (fold) fold.open = true;
        const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        el.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "center" });
        el.focus({ preventScroll: true });
        setFlashN(n);
        flashTimer.current = setTimeout(() => setFlashN(null), FLASH_MS);
      }),
    );
  };

  // "Based on N sittings": the sittings of the sources the answer actually cites. An answer that cites
  // nothing rests on nothing, so it says so rather than counting retrieved sittings.
  const cited = new Set([...answer.matchAll(/\[(\d{1,2})\]/g)].map((m) => Number(m[1])));
  const nSittings = new Set(sources.filter((s) => cited.has(s.n)).map((s) => s.date)).size;
  // The API sends no sources (and a "not_found" event) when retrieval found nothing relevant enough.
  const notFound = phase === "done" && sources.length === 0 && !error;

  // Cited sources are the evidence; the rest were retrieved but not used, so they fold away (never removed).
  const citedSrc = sources.filter((s) => cited.has(s.n));
  const restSrc = sources.filter((s) => !cited.has(s.n));
  const split = phase === "done" && !sawListEarly && citedSrc.length > 0 && restSrc.length > 0;

  // "Quotes checked" is only claimed when the backend check ran clean AND every quote shown as a blockquote is found,
  // word for word, in a source it cites. (The backend check alone accepts a quote found in ANY source, which would
  // let a quote sit under the wrong speaker.)
  const quotes = longQuotes(answer);
  const attributed = quotes.every(([quote, tail]) => citedSources(tail, sources).some((s) => quoteInSource(quote, s)));
  const verified =
    phase === "done" && check !== null && !check.unverified_quotes.length && !check.missing_sources.length && quotes.length > 0 && attributed && nSittings > 0;

  // "Terlalu laju. Cuba lagi sebentar lagi. (HTTP 429)" -> message + code, so the copy isn't doubled up.
  const em = /^(.*?)\s*\(HTTP (\d+)\)$/.exec(error);
  const code = em?.[2];
  const msg = (em ? em[1] : error).replace(/[.\s]+$/, "");
  const limited = code === "429";

  const copy = async () => {
    const lines = sources.map((s) => `[${s.n}] ${s.speaker} · ${s.date_display} · ${s.pdf_url}`);
    try {
      await navigator.clipboard.writeText([answer, "", "Sumber (Penyata Rasmi Dewan Rakyat):", ...lines].join("\n"));
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard blocked: nothing to do */
    }
  };

  // One outcome announced once, instead of every streamed token and every loading joke.
  const SLOW = "Ambil masa lebih lama daripada biasa. Pelayan mungkin baru bangun dan sedang memuatkan model; tunggu sekejap.";
  const statusText = notFound
    ? "Tiada dalam rekod."
    : phase === "searching"
      ? slow
        ? SLOW
        : "Sedang mencari dalam Penyata Rasmi…"
      : phase === "answering"
        ? "Sumber ditemui, jawapan sedang ditulis…"
        : phase === "done" && answer
          ? `Jawapan siap. ${sources.length} sumber.`
          : "";

  const card = (s: Source) => (
    <SourceCard
      key={s.n}
      source={s}
      flash={flashN === s.n}
      ref={(el) => {
        if (el) cardRefs.current.set(s.n, el);
        else cardRefs.current.delete(s.n);
      }}
    />
  );

  return (
    <>
      <p role="status" className="sr-only">
        {statusText}
      </p>
      {/* its own region, so copying doesn't make the first one announce "Jawapan siap" a second time */}
      <p role="status" className="sr-only">
        {copied ? "Jawapan disalin." : ""}
      </p>

      {phase === "searching" ? (
        <div className="space-y-5">
          <p aria-hidden className="text-[14px] text-muted-foreground">
            {LOADING[loadingLine % LOADING.length]}
          </p>
          {slow ? (
            <p aria-hidden className="text-[13px] text-muted-foreground">
              {SLOW}
            </p>
          ) : null}
          {/* the shape of what is coming: the two tabs, the strip of sources, then the answer's lines */}
          <div aria-hidden>
            <div className="flex gap-6 border-b border-line pb-3">
              <Skeleton className="h-4 w-16" />
              <Skeleton className="h-4 w-20" />
            </div>
            <div className="mt-5 flex gap-2 overflow-hidden">
              {[0, 1, 2, 3].map((i) => (
                <div key={i} className="flex h-[92px] w-44 shrink-0 flex-col gap-2 rounded-lg border border-line bg-surface p-3">
                  <Skeleton className="h-5 w-6" />
                  <Skeleton className="h-3 w-[85%]" />
                  <Skeleton className="mt-auto h-3 w-[55%]" />
                </div>
              ))}
            </div>
            <div className="mt-6 max-w-[65ch] space-y-3">
              <Skeleton className="h-4 w-[92%]" />
              <Skeleton className="h-4 w-[84%]" />
              <Skeleton className="h-4 w-[70%]" />
              <Skeleton className="mt-6 h-4 w-[88%]" />
              <Skeleton className="h-4 w-[62%]" />
            </div>
          </div>
        </div>
      ) : null}

      {notFound ? (
        <div className="rise">
          <h2 className="font-heading text-[22px] leading-snug font-medium tracking-[-0.02em]">
            {status && isPartial(status) ? "Tiada dalam sidang yang diindeks." : "Tiada dalam rekod."}
          </h2>
          <p className="mt-2 max-w-[65ch] text-[15px] leading-relaxed text-muted-foreground">
            {status && isPartial(status)
              ? `Kami tak jumpa apa-apa yang berkaitan dalam ${coverage(status)}. Ini tidak bermakna topik itu tidak pernah dibincangkan: sidang lain belum dibaca. Cuba perkataan lain.`
              : "Kami tak jumpa apa-apa yang berkaitan dalam Penyata Rasmi yang diindeks. Cuba perkataan lain."}
            {hasFilters ? " Atau buang penapis." : null}
          </p>
          <div className="mt-5 flex flex-wrap gap-2">
            {hasFilters ? (
              <button type="button" onClick={onClearFilters} className={BTN_SOLID}>
                Buang penapis dan cari semula
              </button>
            ) : null}
            <button type="button" onClick={onEdit} className={BTN_QUIET}>
              Ubah soalan
            </button>
          </div>
        </div>
      ) : null}

      {sources.length || answer ? (
        <div role="tablist" aria-label="Paparan" className="mb-6 flex gap-6 border-b border-line">
          {(["jawapan", "sumber"] as const).map((t) => (
            <button
              key={t}
              type="button"
              role="tab"
              id={`tab-${t}`}
              aria-selected={tab === t}
              aria-controls={`panel-${t}`}
              tabIndex={tab === t ? 0 : -1}
              onKeyDown={(e) => {
                // the tabs pattern: arrow keys move between tabs, Tab leaves the list
                if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
                e.preventDefault();
                const next: Tab = t === "jawapan" ? "sumber" : "jawapan";
                if (next === "sumber" && phase !== "done") setSawListEarly(true);
                setTab(next);
                document.getElementById(`tab-${next}`)?.focus();
              }}
              onClick={() => {
                if (t === "sumber" && phase !== "done") setSawListEarly(true);
                setTab(t);
              }}
              className={cn(
                // the underline is the tab indicator: the one border on this page that carries state
                "-mb-px border-b py-2.5 text-[14px] transition-colors",
                tab === t ? "border-foreground font-medium text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
              )}
            >
              {t === "jawapan" ? "Jawapan" : <>Sumber {sources.length ? <span className="tabular">({sources.length})</span> : null}</>}
            </button>
          ))}
        </div>
      ) : null}

      <div role="tabpanel" id="panel-jawapan" aria-labelledby="tab-jawapan" hidden={tab !== "jawapan"}>
        {sources.length ? (
          <ul aria-label="Sumber" className="-mx-5 -mt-1 mb-5 flex gap-2 overflow-x-auto px-5 py-1 [scrollbar-width:none] sm:-mx-1 sm:px-1 [&::-webkit-scrollbar]:hidden">
            {sources.map((s) => (
              <li key={s.n} className="shrink-0">
                <button
                  type="button"
                  onClick={() => onCite(s.n)}
                  className="flex h-full w-44 flex-col items-start gap-1.5 rounded-lg border border-line bg-surface p-3 text-left transition-colors duration-150 hover:border-muted-foreground"
                >
                  <span className="inline-grid h-5 min-w-6 place-items-center rounded-md border border-line bg-surface px-1 text-[11px] font-medium tabular text-brand">
                    {s.n}
                  </span>
                  <span className="line-clamp-2 text-[13px] leading-snug text-foreground">{s.speaker}</span>
                  <span className="mt-auto text-[12px] text-muted-foreground tabular">{s.date_display}</span>
                </button>
              </li>
            ))}
          </ul>
        ) : null}

        {answer ? (
          <article aria-busy={phase === "answering"} className="rise">
            <Answer
              text={answer}
              sources={sources}
              missing={check?.missing_sources}
              unverified={check?.unverified_quotes}
              streaming={phase === "answering"}
              onCite={onCite}
            />
            {phase === "done" ? (
              <div className="mt-8 flex items-start gap-4 text-[13px] text-muted-foreground">
                <div className="flex min-h-9 min-w-0 flex-1 flex-wrap items-center gap-x-4 gap-y-1">
                  <span className="text-foreground tabular">
                    {nSittings ? `Berdasarkan ${nSittings} persidangan` : "Jawapan ini tidak memetik mana-mana sumber"}
                  </span>
                  {verified ? (
                    <span className="inline-flex items-center gap-1">
                      <CheckIcon className="size-3.5" aria-hidden /> Petikan disemak kata demi kata
                    </span>
                  ) : null}
                  {nSittings ? <span>Ringkasan AI, semak sumber.</span> : null}
                </div>
                <button type="button" onClick={copy} className={`${TEXT_BTN} -me-2 shrink-0`}>
                  {copied ? <CheckIcon className="size-3.5" aria-hidden /> : <Copy className="size-3.5" aria-hidden />}
                  {copied ? "Disalin" : "Salin"}
                </button>
              </div>
            ) : null}
          </article>
        ) : null}

        {check && (check.unverified_quotes.length || check.missing_sources.length) ? (
          <div className="rise mt-6 max-w-[65ch] rounded-xl border border-line bg-surface px-4 py-3 text-[13px] leading-relaxed">
            {check.unverified_quotes.length ? (
              <p>Sebahagian petikan tidak dijumpai kata demi kata dalam sumber; anggap sebagai parafrasa.</p>
            ) : null}
            {check.missing_sources.length ? <p>Rujukan tanpa sumber: [{check.missing_sources.join("], [")}]</p> : null}
          </div>
        ) : null}

      </div>

      {error || phase === "error" ? (
        <div role="alert" className="rise mt-6 max-w-[65ch] rounded-xl border border-line bg-surface px-4 py-4 text-[13px] leading-relaxed">
          <p className="font-medium">{limited ? "Pustakawan perlu tarik nafas sekejap." : "Alamak, pustakawan tersadung."}</p>
          <p className="text-muted-foreground">
            {limited
              ? "Terlalu banyak soalan dalam masa yang singkat. Tunggu sebentar, kemudian cuba lagi."
              : `${msg || "Ralat tidak diketahui"}.`}
          </p>
          <div className="mt-3 flex items-center gap-3">
            <button type="button" onClick={onRetry} className={BTN_SOLID}>
              Cuba lagi
            </button>
            {code ? <span className="text-[12px] text-muted-foreground tabular">HTTP {code}</span> : null}
          </div>
        </div>
      ) : null}


      {sources.length ? (
        <section role="tabpanel" id="panel-sumber" aria-labelledby="tab-sumber" hidden={tab !== "sumber"} className="rise">
          <SourceDates sources={sources} cited={phase === "done" ? cited : new Set()} onCite={onCite} from={status?.from} to={status?.to} />
          <h2 className={LABEL}>
            {split ? "Sumber yang dipetik" : "Sumber"} <span className="tabular">({(split ? citedSrc : sources).length})</span>
          </h2>
          {phase === "done" && answer && !cited.size ? (
            <p className="mt-2 text-[13px] text-muted-foreground">Petikan terdekat yang ditemui. Jawapan di atas tidak bergantung padanya.</p>
          ) : null}
          <ol className="mt-2">{(split ? citedSrc : sources).map(card)}</ol>
          {split ? (
            <details className="group">
              <summary className={`${TEXT_BTN} -mx-2 mt-2 cursor-pointer list-none [&::-webkit-details-marker]:hidden`}>
                {restSrc.length} petikan lain ditemui, tidak dipetik dalam jawapan
                <ChevronDown className="size-4 shrink-0 transition-transform group-open:rotate-180" aria-hidden />
              </summary>
              <ol className="mt-2">{restSrc.map(card)}</ol>
            </details>
          ) : null}
          {meta ? <p className="mt-10 text-[12px] text-muted-foreground tabular">{meta}</p> : null}
        </section>
      ) : null}
    </>
  );
}
