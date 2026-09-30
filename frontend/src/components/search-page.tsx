"use client";

import { ArrowRight, Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";

import { FilterChips } from "@/components/filter-chips";
import { Results } from "@/components/results";
import { Button } from "@/components/ui/button";
import { apiUrl, type Filters, type Status } from "@/lib/api";
import { coverage, isPartial, STARTERS } from "@/lib/copy";

/**
 * Search-first page. The question and filters live in the URL (?q=&speaker=&from=&to=), so a search is a
 * shareable link and there is no chat history (spec: single question, no saved threads).
 */
export function SearchPage() {
  const router = useRouter();
  const pathname = usePathname();
  const params = useSearchParams();
  const q = (params.get("q") ?? "").trim();
  const filters: Filters = { speakerId: params.get("speaker"), party: params.get("party"), dateFrom: params.get("from"), dateTo: params.get("to") };
  const searching = q.length >= 2;

  // the box follows the URL (back/forward, starter clicks) but stays editable in between
  const [draft, setDraft] = useState(q);
  const [shownQ, setShownQ] = useState(q);
  if (shownQ !== q) {
    setShownQ(q);
    setDraft(q);
  }

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

  return (
    <div className="mx-auto w-full max-w-3xl px-4 sm:px-6">
      {/* Search bar on top, filter chips under it */}
      <div className="sticky top-14 z-20 -mx-4 bg-background/90 px-4 pt-4 pb-3 backdrop-blur-md sm:-mx-6 sm:px-6">
        {!searching ? (
          <div className="pt-6 pb-6 sm:pt-12">
            <h1 className="font-heading text-[clamp(30px,6vw,48px)] leading-[1.04] font-bold tracking-[-0.035em] text-balance">
              Tanya apa sahaja tentang Dewan Rakyat.
            </h1>
            <p className="mt-3 max-w-[34em] text-[16px] leading-relaxed text-muted-foreground text-pretty">
              Cari apa yang dikatakan di Dewan Rakyat, dengan petikan kata demi kata dan pautan ke PDF rasmi.
              Pustakawan, bukan pengulas politik.
            </p>
            {status ? (
              <p className="mt-2 text-[13px] text-subtle tabular">
                Buat masa ini: {coverage(status)}
                {isPartial(status) ? ". Pustakawan masih membaca." : "."}
              </p>
            ) : null}
          </div>
        ) : null}
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            if (draft.trim().length >= 2) go({ q: draft });
          }}
          className="flex h-13 items-center gap-2 rounded-full bg-card ps-4 pe-1.5 shadow-[0_0_0_1px_var(--border-default),0_12px_32px_-18px_rgb(0_0_0/0.35)] focus-within:shadow-[0_0_0_2px_var(--ring-focus),0_12px_32px_-18px_rgb(0_0_0/0.35)]"
        >
          <Search className="size-5 shrink-0 text-subtle" aria-hidden />
          <label htmlFor="q" className="sr-only">
            Soalan
          </label>
          <input
            id="q"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            maxLength={500}
            placeholder="Tanya tentang perbahasan Dewan Rakyat…"
            className="h-full min-w-0 flex-1 bg-transparent text-[16px] outline-none placeholder:text-subtle"
            autoComplete="off"
            enterKeyHint="search"
          />
          <Button type="submit" size="icon-lg" className="size-10 rounded-full bg-foreground text-background hover:bg-foreground/85" disabled={draft.trim().length < 2} aria-label="Cari">
            <ArrowRight className="size-5" />
          </Button>
        </form>
        <div className="mt-3">
          <FilterChips value={filters} onChange={(f) => go({ filters: f })} status={status} />
        </div>
      </div>

      <div className="pt-4 pb-24">
        {searching ? (
          <>
            <h1 className="sr-only">Jawapan untuk: {q}</h1>
            <Results key={`${q}|${filters.speakerId ?? ""}|${filters.party ?? ""}|${filters.dateFrom ?? ""}|${filters.dateTo ?? ""}`} question={q} filters={filters} status={status} />
          </>
        ) : (
          <section aria-label="Contoh soalan">
            <p className="mb-3 text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">Cuba tanya</p>
            <div className="grid gap-2.5 sm:grid-cols-2">
              {STARTERS.map((s) => (
                <button
                  key={s}
                  type="button"
                  onClick={() => go({ q: s })}
                  className="group flex items-center justify-between gap-3 rounded-2xl bg-card px-4 py-3.5 text-left text-[14px] leading-snug text-muted-foreground shadow-[0_0_0_1px_var(--border-subtle)] transition-all hover:-translate-y-px hover:text-foreground hover:shadow-[0_0_0_1px_var(--border-default),0_10px_24px_-14px_rgb(0_0_0/0.25)]"
                >
                  {s}
                  <ArrowRight className="size-4 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
