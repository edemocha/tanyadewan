import Link from "next/link";

// Wrapper copy only: the joke is about the tool's own shelves, never about anything in the record.
export default function NotFound() {
  return (
    <div className="mx-auto w-full max-w-2xl px-5 py-24 sm:px-6">
      <h1 className="font-heading text-2xl font-medium tracking-[-0.02em]">Halaman ini tiada dalam rekod.</h1>
      <p className="mt-2 text-[14px] leading-relaxed text-muted-foreground">
        Pustakawan sudah semak rak dua kali. Mungkin pautan lama, atau memang tak pernah wujud.
      </p>
      <Link
        href="/"
        className="mt-5 inline-flex h-10 items-center rounded-lg bg-primary px-4 text-[14px] font-medium text-primary-foreground hover:opacity-85"
      >
        Kembali ke carian
      </Link>
    </div>
  );
}
