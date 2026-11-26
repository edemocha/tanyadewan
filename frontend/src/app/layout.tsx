import type { Metadata } from "next";
import { Instrument_Sans, Inter } from "next/font/google";

import { Sidebar, SiteHeader } from "@/components/site-header";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

// Two weights only, 400 and 500. Inter is variable; the heading face is loaded at 500 alone.
const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const instrument = Instrument_Sans({ variable: "--font-instrument", subsets: ["latin"], weight: ["500"] });

const TITLE = "TanyaDewan";
const DESCRIPTION = "Tanya apa sahaja tentang perbahasan Dewan Rakyat. Setiap jawapan dipautkan ke Penyata Rasmi.";

export const metadata: Metadata = {
  title: TITLE,
  description: DESCRIPTION,
  openGraph: { title: TITLE, description: DESCRIPTION, siteName: "TanyaDewan", locale: "ms_MY", type: "website" },
};

// Runs before first paint: the saved choice wins, otherwise the system preference, otherwise dark (the default).
// Blocked storage (private mode) only loses the saved choice. <html> carries no data-theme in the markup, so React
// never resets what this sets.
const THEME_SCRIPT = `var t=null;try{t=localStorage.getItem("td_theme")}catch(e){}document.documentElement.dataset.theme=t==="light"||t==="dark"?t:matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"`;

const FOOT_LINK = "text-foreground underline underline-offset-4";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ms" suppressHydrationWarning className={`${inter.variable} ${instrument.variable} h-full`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="min-h-full">
        <a
          href="#kandungan"
          className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-50 focus:rounded-lg focus:bg-surface focus:px-4 focus:py-2 focus:text-sm"
        >
          Terus ke kandungan
        </a>
        <TooltipProvider>
          {/* a left rail on desktop, a top bar on phones; the page column fills the rest */}
          <div className="flex min-h-dvh">
            <Sidebar />
            <div className="flex min-w-0 flex-1 flex-col">
              <SiteHeader />
              <main id="kandungan" tabIndex={-1} className="flex flex-1 flex-col outline-none">
                {children}
              </main>
              <footer className="px-5 py-6 text-center text-[12px] leading-relaxed text-muted-foreground sm:px-6">
                <p className="mx-auto max-w-2xl">
                  Sumber: Penyata Rasmi Dewan Rakyat © Parlimen Malaysia. Setiap jawapan dipautkan ke PDF rasmi.
                  TanyaDewan boleh tersilap: semak petikan dengan PDF.
                </p>
                {/* on desktop the credit lives at the foot of the rail */}
                <p className="mt-2 lg:hidden">
                  Dibina oleh{" "}
                  <a href="https://github.com/edemocha" target="_blank" rel="noopener" className={FOOT_LINK}>
                    Danial Adam
                  </a>
                  {" · "}
                  <a href="https://github.com/edemocha/tanyadewan" target="_blank" rel="noopener" className={FOOT_LINK}>
                    kod sumber
                  </a>
                </p>
              </footer>
            </div>
          </div>
        </TooltipProvider>
      </body>
    </html>
  );
}
