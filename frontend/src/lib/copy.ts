import type { Status } from "@/lib/api";

// Wrapper copy. The humour lives here and never in answers, quotes or anything about an MP (CLAUDE.md).

export const LOADING = [
  "Menyelak Penyata Rasmi…",
  "Mencari di bawah timbunan kertas kerja…",
  "Pustakawan sedang memakai cermin mata…",
  "Membaca dengan penuh berkecuali…",
  "Melangkau semua [Tepuk] dan [Dewan riuh]…",
  "Menyemak siapa cakap apa, dua kali…",
];

export const STARTERS = [
  "Apa yang MP cakap pasal PTPTN?",
  "Which MPs raised flood mitigation in Kelantan?",
  "Minister cakap apa bila ditanya pasal harga telur?",
  "Siapa betul pasal isu subsidi diesel?",
];

export const MONTHS_MS = [
  "Januari", "Februari", "Mac", "April", "Mei", "Jun", "Julai", "Ogos", "September", "Oktober", "November", "Disember",
];

export function dateMs(iso: string): string {
  const [y, m, d] = iso.split("-").map(Number);
  return `${d} ${MONTHS_MS[m - 1]} ${y}`;
}

type Coverage = Pick<Status, "sittings_indexed" | "sittings_total" | "from" | "to">;

/** What is actually searchable, e.g. "68 daripada 266 persidangan (10 Oktober 2025 – 11 Ogos 2026)". */
export function coverage(s: Coverage): string {
  const range = s.from && s.to ? ` (${dateMs(s.from)} – ${dateMs(s.to)})` : "";
  return s.sittings_indexed < s.sittings_total
    ? `${s.sittings_indexed} daripada ${s.sittings_total} persidangan${range}`
    : `semua ${s.sittings_total} persidangan${range}`;
}

export const isPartial = (s: Coverage) => s.sittings_indexed < s.sittings_total;

const SMALL_WORDS = new Set(["dan", "di", "bagi", "yang", "ke", "dari", "daripada", "kepada", "untuk", "pada", "dengan", "oleh", "atau"]);

/** Hansard prints headings in capitals. Show them in title case; tokens with digits or dots ("P.M. 14(1)(i)") stay as printed. */
export function headingCase(s: string): string {
  if (s !== s.toUpperCase() || s === s.toLowerCase()) return s;
  return s
    .split(" ")
    .map((w, i) =>
      /[\d.]/.test(w)
        ? w
        : i > 0 && SMALL_WORDS.has(w.toLowerCase())
          ? w.toLowerCase()
          : w.toLowerCase().replace(/(^|-)(\p{L})/gu, (_m, a: string, b: string) => a + b.toUpperCase()),
    )
    .join(" ");
}
