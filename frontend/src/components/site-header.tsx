"use client";

import { Moon, Sun } from "lucide-react";
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

/** A plain top bar on every screen: the logo, the sittings link (when not public) and the theme toggle. */
export function SiteHeader() {
  const path = usePathname();
  return (
    <header className="h-14 lg:h-16">
      <div className="mx-auto flex h-full w-full max-w-[1104px] items-center gap-4 px-5 sm:px-8">
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
