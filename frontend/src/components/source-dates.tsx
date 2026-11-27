import type { Source } from "@/lib/api";
import { cn } from "@/lib/utils";

/**
 * When the excerpts found for this question were said: one column per sitting date, one block per excerpt.
 * It charts only the excerpts retrieved for this answer (a handful), never how often a topic came up in the whole
 * record: that needs a count from the backend, and the caption says so. Blocks are the citation numbers themselves,
 * so the chart doubles as a way into the list. No colour carries meaning beyond cited (solid) and not cited (outline).
 */
export function SourceDates({ sources, cited, onCite }: { sources: Source[]; cited: Set<number>; onCite: (n: number) => void }) {
  const byDate = new Map<string, Source[]>();
  for (const s of [...sources].sort((a, b) => a.date.localeCompare(b.date) || a.n - b.n)) {
    byDate.set(s.date, [...(byDate.get(s.date) ?? []), s]);
  }
  // one sitting is not a spread worth drawing
  if (byDate.size < 2) return null;
  const anyCited = sources.some((s) => cited.has(s.n));

  return (
    <figure className="mb-8">
      <figcaption className="text-[12px] tracking-[0.08em] text-muted-foreground uppercase">Petikan mengikut tarikh sidang</figcaption>
      <ol className="mt-3 flex items-end gap-1 overflow-x-auto border-b border-line pb-px [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        {[...byDate].map(([date, group]) => (
          <li key={date} className="flex min-w-16 flex-1 flex-col items-center gap-1">
            {/* newest block on top, so a taller column reads as "more was found from this sitting" */}
            <div className="flex flex-col-reverse items-center gap-1">
              {group.map((s) => (
                <button
                  key={s.n}
                  type="button"
                  onClick={() => onCite(s.n)}
                  aria-label={`Sumber ${s.n}: ${s.speaker}, ${s.date_display}${cited.has(s.n) ? ", dipetik dalam jawapan" : ""}`}
                  className={cn(
                    "relative grid h-6 w-10 place-items-center rounded-md border text-[11px] font-medium tabular transition-colors duration-150 before:absolute before:-inset-x-1 before:-inset-y-0.5 before:content-['']",
                    cited.has(s.n)
                      ? "border-foreground bg-foreground text-background hover:opacity-85"
                      : "border-line bg-surface text-muted-foreground hover:border-muted-foreground hover:text-foreground",
                  )}
                >
                  {s.n}
                </button>
              ))}
            </div>
            <span className="pt-1 pb-2 text-center text-[11px] leading-tight text-muted-foreground tabular">{shortDate(group[0])}</span>
          </li>
        ))}
      </ol>
      <p className="mt-2 text-[12px] leading-relaxed text-muted-foreground">
        {sources.length} petikan yang ditemui untuk soalan ini{anyCited ? "; yang gelap dipetik dalam jawapan" : ""}. Bukan kiraan semua sebutan dalam
        rekod.
      </p>
    </figure>
  );
}

/** "3 November 2025" -> "3 Nov 2025": the columns are narrow. */
function shortDate(s: Source): string {
  const [d, m, y] = s.date_display.split(" ");
  return m && y ? `${d} ${m.slice(0, 3)} ${y}` : s.date_display;
}
