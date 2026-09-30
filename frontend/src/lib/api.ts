// Types and calls for the FastAPI backend (src/tanyadewan/api). The browser goes through the /api rewrite in
// next.config.ts; server components call the backend directly.

export type Source = {
  n: number;
  turn_id: string;
  speaker: string;
  speaker_id: string | null;
  constituency: string | null;
  role: string | null;
  party?: string | null;
  terms?: string[];
  resolution: string | null;
  unattributed: boolean;
  date: string;
  date_display: string;
  section: string | null;
  section_heading: string | null;
  page_label: string | null;
  pdf_url: string;
  is_draft: boolean;
  ocr: boolean;
  text: string;
  part: number | null;
  n_parts: number | null;
  score: number;
  photo_url: string | null;
  profile_url: string | null;
  initials: string;
};

export type Check = { unverified_quotes: string[]; missing_sources: number[] };

export type Filters = { speakerId?: string | null; party?: string | null; dateFrom?: string | null; dateTo?: string | null };

export type PartyOption = { party: string; members: number };

export type Speaker = { id: string; label: string };

export type Status = {
  sittings_indexed: number;
  sittings_total: number;
  chunks: number;
  engine: string;
  from: string | null;
  to: string | null;
};

export type SittingSummary = {
  doc_id: string;
  date: string;
  date_display: string;
  penggal: number | null;
  mesyuarat: number | null;
  mesyuarat_title: string | null;
  bil: number | null;
  is_draft: boolean;
  n_turns: number;
  pdf_url: string;
};

export type SittingTurn = {
  turn_id: string;
  speaker: string;
  speaker_id: string | null;
  role: string | null;
  constituency: string | null;
  resolution: string | null;
  unattributed: boolean;
  is_interjection: boolean;
  initials: string;
  photo_url: string | null;
  page_label: string | null;
  ocr: boolean;
  pdf_url: string;
  text: string;
};

export type Sitting = SittingSummary & {
  sections: { heading: string; section: string | null; turns: SittingTurn[] }[];
};

/** Public deployment: the API lives on another origin (NEXT_PUBLIC_API_BASE), so the browser calls it directly. */
export const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "";
/** Public deployment shows cited excerpts only: no full-transcript browsing (NEXT_PUBLIC_PUBLIC_MODE=1). */
export const PUBLIC_MODE = process.env.NEXT_PUBLIC_PUBLIC_MODE === "1";
export const apiUrl = (path: string) => `${API_BASE}${path}`;

/** Server-side base URL (server components can't use the relative /api rewrite). */
export const SERVER_API = process.env.TANYADEWAN_API ?? "http://127.0.0.1:8766";

export type AskEvent =
  | { event: "sources"; data: Source[] }
  | { event: "engine"; data: string }
  | { event: "token"; data: string }
  | { event: "check"; data: Check }
  | { event: "not_found"; data: { best_relevance: number | null; threshold: number; mode: string; reranked: boolean } }
  | { event: "error"; data: string }
  | { event: "done"; data: { retrieve_ms?: number; generate_ms?: number } };

/** POST /api/ask and yield its server-sent events as they arrive. */
export async function* ask(question: string, filters: Filters, signal: AbortSignal): AsyncGenerator<AskEvent> {
  const res = await fetch(apiUrl("/api/ask"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      question,
      date_from: filters.dateFrom || null,
      date_to: filters.dateTo || null,
      speaker_id: filters.speakerId || null,
      party: filters.party || null,
    }),
    signal,
  });
  if (!res.ok || !res.body) {
    let detail = res.statusText;
    try {
      detail = (await res.json()).detail ?? detail;
    } catch {
      /* not JSON */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const block = buf.slice(0, i);
      buf = buf.slice(i + 2);
      const event = /^event: (.+)$/m.exec(block)?.[1];
      const data = /^data: (.*)$/m.exec(block)?.[1];
      if (event && data !== undefined) yield { event, data: JSON.parse(data) } as AskEvent;
    }
  }
}
