import { ChevronRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Badge } from "@/components/ui/badge";
import { PUBLIC_MODE, SERVER_API, type SittingSummary } from "@/lib/api";

export const metadata: Metadata = { title: "Sidang · TanyaDewan" };
export const dynamic = "force-dynamic"; // the list grows as sittings are parsed

async function getSittings(): Promise<SittingSummary[] | null> {
  try {
    const res = await fetch(`${SERVER_API}/api/sittings`, { cache: "no-store" });
    return res.ok ? res.json() : null;
  } catch {
    return null;
  }
}

export default async function SittingsPage() {
  if (PUBLIC_MODE) notFound();
  const sittings = await getSittings();
  if (!sittings) {
    return (
      <p className="mx-auto max-w-3xl px-4 py-16 text-muted-foreground sm:px-6">
        Pelayan API belum hidup. Jalankan <code>uv run python -m tanyadewan.api</code>, kemudian muat semula.
      </p>
    );
  }
  // group by meeting (Penggal / Mesyuarat), newest first, as the Hansard itself is organised
  const groups = new Map<string, SittingSummary[]>();
  for (const s of sittings) {
    const key = s.mesyuarat_title ?? `Penggal ${s.penggal} · Mesyuarat ${s.mesyuarat}`;
    groups.set(key, [...(groups.get(key) ?? []), s]);
  }

  return (
    <div className="mx-auto max-w-3xl px-4 pt-10 pb-24 sm:px-6">
      <h1 className="font-heading text-[clamp(28px,5vw,40px)] leading-tight font-bold tracking-[-0.03em]">Sidang</h1>
      <p className="mt-2 text-muted-foreground tabular">
        {sittings.length} persidangan Dewan Rakyat, Parlimen ke-15. Buka satu untuk membaca Penyata Rasminya.
      </p>

      <div className="mt-10 space-y-10">
        {[...groups.entries()].map(([title, rows]) => (
          <section key={title} aria-label={title}>
            <h2 className="mb-2 text-[11px] font-semibold tracking-[0.08em] text-subtle uppercase">
              {rows[0].penggal && !/penggal/i.test(title) ? `Penggal ${rows[0].penggal} · ` : ""}
              {title}
            </h2>
            <ul className="overflow-hidden rounded-2xl bg-card shadow-[0_0_0_1px_var(--border-subtle)]">
              {rows.map((s) => (
                <li key={s.doc_id} className="border-b last:border-b-0">
                  <Link
                    href={`/sidang/${s.doc_id}`}
                    className="group flex items-center gap-4 px-4 py-3.5 transition-colors hover:bg-muted sm:px-5"
                  >
                    <span className="w-40 shrink-0 font-medium tabular">{s.date_display}</span>
                    <span className="hidden text-[13px] text-subtle tabular sm:inline">{s.bil ? `Bil. ${s.bil}` : ""}</span>
                    <span className="ms-auto flex items-center gap-2 text-[13px] text-muted-foreground tabular">
                      {s.is_draft ? <Badge className="bg-warning text-warning-foreground">draf</Badge> : null}
                      {s.n_turns.toLocaleString("ms-MY")} giliran
                      <ChevronRight className="size-4 text-subtle transition-transform group-hover:translate-x-0.5" />
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
