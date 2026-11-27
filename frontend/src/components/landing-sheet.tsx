import { ArrowUpRight } from "lucide-react";

/**
 * The landing page's picture: a page of Hansard with one line marked, which is the whole product in a glance
 * (find the exact line, name who said it, link the page).
 *
 * Everything readable on it is real: the running head is the one printed on that page ("38", "DR.3.11.2025"), and
 * the marked line is a turn copied verbatim from the parsed record (turn DR-2025-11-03:0224, printed page 38,
 * page 46 of the PDF), set the way Hansard sets a turn: speaker in bold, then the words. Every other turn on the
 * page is drawn as blank lines: never invented transcript text, and no other member's words out of context.
 */
const QUOTE = {
  speaker: "Datuk Che Mohamad Zulkifly bin Jusoh [Besut]",
  text: "Menteri, yang lain-lain tu macam mana? Ada PTPTN tu.",
  date: "3 November 2025",
  page: "38",
  runningHead: "DR.3.11.2025",
  href: "https://www.parlimen.gov.my/files/hindex/pdf/DR-03112025.pdf#page=46",
};

/** One turn nobody needs to read: a darker stub where the speaker's name would be, then lines of "text". */
function Turn({ name, lines, className }: { name: string; lines: string[]; className?: string }) {
  return (
    <div aria-hidden className={`flex flex-col gap-[9px] ${className ?? ""}`}>
      {lines.map((w, i) => (
        <div key={i} className="flex h-[7px] gap-2" style={{ width: w }}>
          {i === 0 ? <span className="rounded-full bg-muted-foreground/45" style={{ width: name }} /> : null}
          <span className="flex-1 rounded-full bg-line" />
        </div>
      ))}
    </div>
  );
}

export function LandingSheet() {
  return (
    <div className="relative mx-auto w-full @4xl:max-w-[468px]">
      {/* a second, empty page behind for depth */}
      <div aria-hidden className="absolute inset-0 hidden -rotate-[2.2deg] rounded-xl border border-line bg-surface @4xl:block" />

      <figure className="elev relative flex flex-col rounded-xl border border-line bg-surface px-5 pt-5 pb-7 @4xl:rotate-[1.2deg] @4xl:px-10 @4xl:pt-8 @4xl:pb-11">
        {/* the running head as printed: page number at the edge, sitting date in the middle */}
        <figcaption className="grid grid-cols-[1fr_auto_1fr] items-baseline border-b border-line pb-3 font-serif text-[12px] leading-4 text-muted-foreground tabular">
          <span>
            <span className="sr-only">Penyata Rasmi Dewan Rakyat, halaman </span>
            {QUOTE.page}
          </span>
          <span>{QUOTE.runningHead}</span>
          <span />
        </figcaption>

        <Turn name="38%" lines={["100%", "96%", "62%"]} className="mt-6" />
        <Turn name="30%" lines={["100%", "44%"]} className="mt-[18px]" />
        <Turn name="42%" lines={["100%", "98%", "100%", "71%"]} className="mt-[18px] hidden @4xl:flex" />

        {/* the one turn that is read: set like the record, speaker in bold and the words after the colon */}
        <blockquote className="mt-5 font-serif text-[18px] leading-[30px] text-foreground @4xl:text-[19px] @4xl:leading-[32px]">
          <span className="font-medium">{QUOTE.speaker}:</span> <mark className="sheet-mark">{QUOTE.text}</mark>
        </blockquote>

        {/* the citation sits right under the line it belongs to, level (not tilted with the page) and overhanging its edge */}
        <div className="elev mt-3 flex w-fit flex-col gap-0.5 self-end rounded-lg border border-line bg-surface px-3.5 py-2.5 font-sans text-[13px] leading-5 @4xl:-me-16 @4xl:-rotate-[1.2deg]">
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

        <Turn name="34%" lines={["100%", "58%"]} className="mt-4" />
        <Turn name="40%" lines={["100%", "97%", "83%"]} className="mt-[18px]" />
        <Turn name="28%" lines={["100%", "36%"]} className="mt-[18px] hidden @4xl:flex" />
      </figure>
    </div>
  );
}
