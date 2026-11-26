import { ArrowLeft, ArrowUpRight } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { SpeakerAvatar } from "@/components/speaker-avatar";
import { Badge } from "@/components/ui/badge";
import { PUBLIC_MODE, SERVER_API, type Sitting } from "@/lib/api";
import { dateMs } from "@/lib/copy";
import { cn } from "@/lib/utils";

export const dynamic = "force-dynamic";

async function getSitting(id: string): Promise<Sitting | null> {
  const res = await fetch(`${SERVER_API}/api/sittings/${encodeURIComponent(id)}`, { cache: "no-store" });
  if (res.status === 404) return null;
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

export async function generateMetadata({ params }: PageProps<"/sidang/[id]">): Promise<Metadata> {
  const { id } = await params;
  const iso = /^DR-(\d{4}-\d{2}-\d{2})$/.exec(id)?.[1];
  return { title: `${iso ? dateMs(iso) : id} · TanyaDewan` };
}

export default async function SittingPage({ params }: PageProps<"/sidang/[id]">) {
  if (PUBLIC_MODE) notFound();
  const { id } = await params;
  const sitting = await getSitting(id);
  if (!sitting) notFound();

  return (
    <div className="mx-auto grid w-full max-w-5xl gap-10 px-4 pt-8 pb-24 sm:px-6 lg:grid-cols-[1fr_15rem]">
      <article className="min-w-0">
        <Link href="/sidang" className="inline-flex items-center gap-1 text-[13px] text-muted-foreground hover:text-foreground">
          <ArrowLeft className="size-3.5" /> Semua sidang
        </Link>
        <h1 className="mt-4 font-heading text-[clamp(26px,4.6vw,38px)] leading-tight font-medium tracking-[-0.03em] tabular">
          {sitting.date_display}
        </h1>
        <p className="mt-1.5 text-[14px] text-muted-foreground">
          {[sitting.penggal ? `Penggal ${sitting.penggal}` : null, sitting.mesyuarat_title, sitting.bil ? `Bil. ${sitting.bil}` : null]
            .filter(Boolean)
            .join(" · ")}
        </p>
        <div className="mt-4 flex flex-wrap items-center gap-3 text-[13px]">
          <a
            href={sitting.pdf_url}
            target="_blank"
            rel="noopener"
            className="inline-flex items-center gap-1 font-medium text-brand underline-offset-2 hover:underline"
          >
            PDF rasmi <ArrowUpRight className="size-3.5" />
          </a>
          {sitting.is_draft ? (
            <Badge className="bg-surface font-normal text-muted-foreground">naskhah draf: belum disemak</Badge>
          ) : null}
          <span className="text-muted-foreground tabular">{sitting.n_turns.toLocaleString("ms-MY")} giliran bercakap</span>
        </div>

        <div className="mt-10 space-y-12">
          {sitting.sections.map((sec, si) => (
            <section key={si} id={`bahagian-${si}`} className="scroll-mt-20">
              {sec.heading ? (
                <h2 className="mb-5 font-heading text-[13px] font-medium tracking-[0.06em] text-muted-foreground uppercase">
                  {sec.heading}
                </h2>
              ) : null}
              <ol className="space-y-5">
                {sec.turns.map((t) => {
                  const named = Boolean(t.speaker_id) && !t.unattributed;
                  return (
                    <li
                      key={t.turn_id}
                      id={t.turn_id}
                      className={cn(
                        "flex scroll-mt-24 gap-3 rounded-xl target:bg-surface target:p-3",
                        t.is_interjection && "ms-8 sm:ms-12",
                      )}
                    >
                      <SpeakerAvatar
                        speaker={t.speaker}
                        initials={t.initials}
                        photoUrl={t.photo_url}
                        named={named}
                        size={t.is_interjection ? "sm" : "default"}
                        className="mt-0.5"
                      />
                      <div className="min-w-0 flex-1">
                        <p className="flex flex-wrap items-baseline gap-x-2 text-[13.5px]">
                          <span className="font-medium">{t.speaker}</span>
                          {t.ocr ? <Badge className="bg-surface font-normal text-muted-foreground">OCR</Badge> : null}
                          <a
                            href={t.pdf_url}
                            target="_blank"
                            rel="noopener"
                            className="text-[12px] text-muted-foreground tabular hover:text-foreground"
                          >
                            hlm. {t.page_label ?? "?"}
                          </a>
                        </p>
                        <p
                          className={cn(
                            "mt-1 leading-relaxed whitespace-pre-line text-pretty",
                            t.is_interjection ? "text-[14px] text-muted-foreground" : "text-[15px]",
                          )}
                        >
                          {t.text}
                        </p>
                      </div>
                    </li>
                  );
                })}
              </ol>
            </section>
          ))}
        </div>
      </article>

      <aside className="hidden lg:block">
        <nav aria-label="Bahagian" className="sticky top-24">
          <p className="mb-3 text-[11px] font-medium tracking-[0.08em] text-muted-foreground uppercase">Bahagian</p>
          <ol className="space-y-1 border-s text-[13px]">
            {sitting.sections.map((sec, si) =>
              sec.heading ? (
                <li key={si}>
                  <a
                    href={`#bahagian-${si}`}
                    className="-ms-px block border-s border-transparent py-1 ps-3 leading-snug text-muted-foreground hover:border-foreground hover:text-foreground"
                  >
                    {sec.heading.charAt(0) + sec.heading.slice(1).toLowerCase()}
                  </a>
                </li>
              ) : null,
            )}
          </ol>
        </nav>
      </aside>
    </div>
  );
}
