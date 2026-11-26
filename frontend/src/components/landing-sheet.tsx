import { ArrowUpRight } from "lucide-react";

/**
 * The landing page's picture: a sheet of Hansard with one line highlighted, which is the whole product in a glance
 * (find the exact line, name who said it, link the page).
 *
 * The highlighted line is a real turn, copied verbatim from the parsed record (turn DR-2025-11-03:0224, printed
 * page 38, page 46 of the PDF). Everything else on the sheet is blank bars: never invented transcript text.
 */
const QUOTE = {
  speaker: "Datuk Che Mohamad Zulkifly bin Jusoh [Besut]",
  text: "Menteri, yang lain-lain tu macam mana? Ada PTPTN tu.",
  date: "3 November 2025",
  page: "38",
  href: "https://www.parlimen.gov.my/files/hindex/pdf/DR-03112025.pdf#page=46",
};

function Bars({ widths, className }: { widths: string[]; className: string }) {
  return (
    <div aria-hidden className={`flex flex-col gap-3 ${className}`}>
      {widths.map((w, i) => (
        <div key={i} className="h-2.5 rounded-full bg-line" style={{ width: w }} />
      ))}
    </div>
  );
}

export function LandingSheet() {
  return (
    <div className="relative mx-auto w-full @4xl:max-w-[468px]">
      {/* a second, empty sheet behind for depth */}
      <div aria-hidden className="absolute inset-0 hidden -rotate-[2.2deg] rounded-xl border border-line bg-surface @4xl:block" />

      <figure className="elev relative flex flex-col rounded-xl border border-line bg-surface px-5 py-6 @4xl:rotate-[1.2deg] @4xl:px-10 @4xl:pt-10 @4xl:pb-26">
        <figcaption className="flex items-baseline justify-between gap-3 border-b border-line pb-3 text-[11px] leading-4 tracking-[0.08em] text-muted-foreground uppercase">
          <span>Penyata Rasmi Dewan Rakyat</span>
          <span className="shrink-0 tabular">hlm. {QUOTE.page}</span>
        </figcaption>

        <Bars widths={["34%", "100%", "94%", "98%", "58%"]} className="mt-7" />
        <Bars widths={["28%", "96%", "72%"]} className="mt-6 hidden @4xl:flex" />

        <p className="mt-7 mb-2 text-[13px] leading-5 font-medium">{QUOTE.speaker}:</p>
        <blockquote className="font-serif text-[20px] leading-[32px] @4xl:text-[22px] @4xl:leading-[34px]">
          <mark className="sheet-mark">{QUOTE.text}</mark>
        </blockquote>

        <Bars widths={["31%", "97%", "100%", "91%", "44%"]} className="mt-7" />
      </figure>

      {/* the citation, pinned to the sheet and not tilted with it */}
      <div className="elev mt-3 flex flex-col gap-1 rounded-lg border border-line bg-surface px-3.5 py-3 text-[13px] leading-5 @4xl:absolute @4xl:-right-7 @4xl:bottom-9 @4xl:mt-0">
        <span className="text-muted-foreground tabular">{QUOTE.date}</span>
        <a
          href={QUOTE.href}
          target="_blank"
          rel="noreferrer"
          className="inline-flex min-h-9 items-center gap-1 whitespace-nowrap text-brand transition-opacity duration-150 hover:opacity-70 @4xl:min-h-6"
        >
          Lihat dalam Hansard, hlm. {QUOTE.page}
          <ArrowUpRight className="size-3.5" aria-hidden />
          <span className="sr-only">(PDF, tab baharu)</span>
        </a>
      </div>
    </div>
  );
}
