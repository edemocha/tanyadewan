"use client";

import { BookOpen, Moon, Search, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

import { LogoMark } from "@/components/logo-mark";
import { PUBLIC_MODE } from "@/lib/api";
import { cn } from "@/lib/utils";

// The theme lives on <html data-theme>, set before paint by the script in layout.tsx; read it from there.
function subscribeTheme(onChange: () => void) {
  const o = new MutationObserver(onChange);
  o.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => o.disconnect();
}

function ThemeToggle() {
  // null on the server and until hydration: the theme is only known in the browser, so no icon is guessed
  const theme = useSyncExternalStore<string | null>(
    subscribeTheme,
    () => document.documentElement.dataset.theme ?? "dark",
    () => null,
  );
  const dark = theme !== "light";
  const flip = () => {
    const next = dark ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem("td_theme", next);
    } catch {
      /* private mode: the theme just won't persist */
    }
  };
  return (
    <button
      type="button"
      onClick={flip}
      aria-label={dark ? "Tema cerah" : "Tema gelap"}
      className="grid size-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-hover hover:text-foreground"
    >
      {theme === null ? null : dark ? <Sun className="size-[18px]" aria-hidden /> : <Moon className="size-[18px]" aria-hidden />}
    </button>
  );
}

function Logo({ className }: { className?: string }) {
  return (
    <Link
      href="/"
      aria-label="TanyaDewan"
      className={cn("flex items-center gap-2 rounded-lg font-heading text-[18px] font-medium tracking-[-0.02em]", className)}
    >
      <LogoMark className="size-6 shrink-0" />
      <span>
        TanyaDewan<span className="text-brand">.</span>
      </span>
    </Link>
  );
}

const NAV = [
  { href: "/", label: "Cari", icon: Search },
  ...(PUBLIC_MODE ? [] : [{ href: "/sidang", label: "Sidang", icon: BookOpen }]),
];

const FOOT_LINK = "text-foreground underline underline-offset-4";

/**
 * Desktop: a left rail, as in the answer-engine layout this page follows: logo, navigation, and at the bottom the
 * credit and the theme toggle. The hairline is the one edge that separates the rail from the page.
 */
export function Sidebar() {
  const path = usePathname();
  return (
    <aside className="sticky top-0 hidden h-dvh w-56 shrink-0 flex-col border-e border-line px-3 py-4 lg:flex">
      <Logo className="px-2 py-1" />
      <nav aria-label="Utama" className="mt-6 grid gap-0.5">
        {NAV.map((n) => {
          const on = n.href === "/" ? path === "/" : path.startsWith(n.href);
          return (
            <Link
              key={n.href}
              href={n.href}
              aria-current={on ? "page" : undefined}
              className={cn(
                "flex h-9 items-center gap-2.5 rounded-lg px-2 text-[14px] transition-colors hover:bg-hover",
                on ? "bg-hover text-foreground" : "text-muted-foreground hover:text-foreground",
              )}
            >
              <n.icon className="size-4" aria-hidden />
              {n.label}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex items-end justify-between gap-2 ps-2">
        <p className="pb-2.5 text-[12px] leading-relaxed text-muted-foreground">
          Dibina oleh{" "}
          <a href="https://github.com/edemocha" target="_blank" rel="noopener" className={FOOT_LINK}>
            Danial Adam
          </a>
          <br />
          <a href="https://github.com/edemocha/tanyadewan" target="_blank" rel="noopener" className={FOOT_LINK}>
            kod sumber
          </a>
        </p>
        <ThemeToggle />
      </div>
    </aside>
  );
}

/** Phones and tablets: a plain top bar with the logo and the theme toggle. */
export function SiteHeader() {
  const path = usePathname();
  return (
    <header className="h-14 lg:hidden">
      <div className="flex h-full items-center gap-4 px-5 sm:px-6">
        <Logo />
        {PUBLIC_MODE ? null : (
          <Link
            href="/sidang"
            aria-current={path.startsWith("/sidang") ? "page" : undefined}
            className={cn(
              "rounded-lg px-2 py-1.5 text-[14px] transition-colors hover:bg-hover",
              path.startsWith("/sidang") ? "text-foreground" : "text-muted-foreground",
            )}
          >
            Sidang
          </Link>
        )}
        <div className="ms-auto -me-2.5">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
