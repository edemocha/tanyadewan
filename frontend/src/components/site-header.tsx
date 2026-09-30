"use client";

import { Moon, Sun } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useSyncExternalStore } from "react";

import { PUBLIC_MODE } from "@/lib/api";
import { cn } from "@/lib/utils";

const NAV = [
  { href: "/", label: "Cari" },
  ...(PUBLIC_MODE ? [] : [{ href: "/sidang", label: "Sidang" }]),
];

// The theme lives on <html data-theme> (set before paint by the layout script); read it from there.
function subscribeTheme(onChange: () => void) {
  const o = new MutationObserver(onChange);
  o.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
  return () => o.disconnect();
}

function ThemeToggle() {
  const dark = useSyncExternalStore(
    subscribeTheme,
    () => document.documentElement.dataset.theme === "dark",
    () => false,
  );
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
      className="grid size-9 place-items-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground"
    >
      {dark ? <Sun className="size-[18px]" /> : <Moon className="size-[18px]" />}
    </button>
  );
}

export function SiteHeader() {
  const path = usePathname();
  return (
    <header className="sticky top-0 z-30 h-14 border-b bg-background/85 backdrop-blur-md">
      <div className="mx-auto flex h-full max-w-5xl items-center gap-4 px-4 sm:px-6">
        <Link href="/" aria-label="TanyaDewan" className="flex flex-col font-heading text-[15px] leading-[0.92] tracking-[-0.03em]">
          <span className="font-bold">Tanya</span>
          <span className="font-medium text-subtle">Dewan.</span>
        </Link>
        <nav className="ms-2 flex items-center gap-1 text-[14px]">
          {NAV.map((n) => {
            const on = n.href === "/" ? path === "/" : path.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                className={cn(
                  "rounded-full px-3 py-1.5 transition-colors",
                  on ? "bg-muted font-medium text-foreground" : "text-muted-foreground hover:text-foreground",
                )}
              >
                {n.label}
              </Link>
            );
          })}
        </nav>
        <div className="ms-auto">
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
