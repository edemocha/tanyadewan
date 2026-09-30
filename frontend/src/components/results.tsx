"use client";

import { AlertTriangle, Check as CheckIcon, Copy, FileQuestion } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { Answer } from "@/components/answer";
import { SourceCard } from "@/components/source-card";
import { Skeleton } from "@/components/ui/skeleton";
import { ask, type Check, type Filters, type Source, type Status } from "@/lib/api";
import { coverage, isPartial, LOADING } from "@/lib/copy";

type Phase = "searching" | "answering" | "done" | "error";

// A hosted backend can be slow to wake (it loads about 1.2 GB of models on a cold start): say so after this long,
// and give up rather than show a spinner forever.
const SLOW_AFTER_MS = 20_000;
const GIVE_UP_AFTER_MS = 120_000;

/**
 * One search: streams /api/ask and shows the answer, the "based on N sittings" line and the source cards.
 * The parent keys this component by question + filters, so every new search starts from a clean state.
 */
export function Results({ question, filters, status }: { question: string; filters: Filters; status: Status | null }) {
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
  const cardRefs = useRef(new Map<number, HTMLLIElement>());

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

  const onCite = (n: number) => {
    const el = cardRefs.current.get(n);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    setFlashN(null);
    requestAnimationFrame(() => setFlashN(n));
  };

  // "Based on N sittings": the sittings of the sources the answer actually cites. An answer that cites
  // nothing rests on nothing, so it says so rather than counting retrieved sittings.
  const cited = new Set([...answer.matchAll(/\[(\d{1,2})\]/g)].map((m) => Number(m[1])));
  const nSittings = new Set(sources.filter((s) => cited.has(s.n)).map((s) => s.date)).size;
  // The API sends no sources (and a "not_found" event) when retrieval found nothing relevant enough.
  const notFound = phase === "done" && sources.length === 0 && !error;

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

  return (
    <>
      {phase === "searching" ? (
        <div aria-live="polite" className="space-y-4">
          <p className="text-[14px] text-muted-foreground">{LOADING[loadingLine % LOADING.length]}</p>
          <div className="max-w-[68ch] space-y-2.5">
            <Skeleton className="h-4 w-[92%]" />
            <Skeleton className="h-4 w-[84%]" />
            <Skeleton className="h-4 w-[70%]" />
          </div>
          {slow ? (
            <p className="text-[13px] text-subtle">
              Ambil masa lebih lama daripada biasa. Pelayan mungkin baru bangun dan sedang memuatkan model; tunggu
              sekejap.
            </p>
          ) : null}
        </div>
      ) : null}

      {notFound ? (
        <div className="rounded-2xl bg-card p-6 shadow-[0_0_0_1px_var(--border-subtle)]">
          <FileQuestion className="size-6 text-subtle" />
          <h2 className="mt-3 font-heading text-lg font-semibold tracking-[-0.01em]">
            {status && isPartial(status) ? "Tiada dalam sidang yang diindeks." : "Tiada dalam rekod."}
          </h2>
          <p className="mt-1 text-[14px] leading-relaxed text-muted-foreground">
            {status && isPartial(status)
              ? `Kami tak jumpa apa-apa yang berkaitan dalam ${coverage(status)}. Ini tidak bermakna topik itu tidak pernah dibincangkan: sidang lain belum dibaca. Cuba perkataan lain, atau buang penapis.`
              : "Kami tak jumpa apa-apa yang berkaitan dalam Penyata Rasmi yang diindeks. Cuba perkataan lain, atau buang penapis."}
          </p>
        </div>
      ) : null}

      {answer ? (
        <article aria-live="polite">
          <Answer
            text={answer}
            sources={sources}
            missing={check?.missing_sources}
            unverified={check?.unverified_quotes}
            streaming={phase === "answering"}
            onCite={onCite}
          />
          {phase === "done" ? (
            <div className="mt-5 flex flex-wrap items-center gap-x-3 gap-y-2 text-[12.5px] text-subtle">
              <span>
                {nSittings
                  ? `Berdasarkan ${nSittings} persidangan. Ringkasan AI, semak sumber.`
                  : "Jawapan ini tidak memetik mana-mana sumber."}
              </span>
              <button
                type="button"
                onClick={copy}
                className="inline-flex min-h-8 items-center gap-1 rounded-full px-2.5 text-muted-foreground hover:bg-muted hover:text-foreground"
              >
                {copied ? <CheckIcon className="size-3.5" /> : <Copy className="size-3.5" />}
                {copied ? "Disalin" : "Salin"}
              </button>
            </div>
          ) : null}
        </article>
      ) : null}

      {check && (check.unverified_quotes.length || check.missing_sources.length) ? (
        <div className="mt-4 flex gap-2 rounded-xl bg-warning-subtle px-4 py-3 text-[13px] leading-relaxed">
          <AlertTriangle className="mt-0.5 size-4 shrink-0" />
          <div>
            {check.unverified_quotes.length ? (
              <p>Sebahagian petikan tidak dijumpai kata demi kata dalam sumber; anggap sebagai parafrasa.</p>
            ) : null}
            {check.missing_sources.length ? <p>Rujukan tanpa sumber: [{check.missing_sources.join("], [")}]</p> : null}
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="mt-4 rounded-xl bg-error-subtle px-4 py-3 text-[13px] shadow-[inset_0_0_0_1px_var(--border-error)]">
          Alamak, pustakawan tersadung: {error}. Cuba lagi.
        </p>
      ) : null}

      {sources.length ? (
        <section aria-labelledby="sumber" className="mt-10">
          <h2 id="sumber" className="font-heading text-[17px] font-semibold tracking-[-0.01em]">
            Sumber <span className="text-subtle tabular">({sources.length})</span>
          </h2>
          {phase === "done" && answer && !cited.size ? (
            <p className="mt-1 text-[13px] text-subtle">Petikan terdekat yang ditemui. Jawapan di atas tidak bergantung padanya.</p>
          ) : null}
          <div className="mb-3" />
          <ol className="grid gap-3">
            {sources.map((s) => (
              <SourceCard
                key={s.n}
                source={s}
                flash={flashN === s.n}
                ref={(el) => {
                  if (el) cardRefs.current.set(s.n, el);
                  else cardRefs.current.delete(s.n);
                }}
              />
            ))}
          </ol>
          {meta ? <p className="mt-6 text-[11.5px] text-subtle tabular">{meta}</p> : null}
        </section>
      ) : null}
    </>
  );
}
