import type { Metadata } from "next";
import { Instrument_Sans, Inter } from "next/font/google";

import { SiteHeader } from "@/components/site-header";
import { TooltipProvider } from "@/components/ui/tooltip";
import "./globals.css";

const inter = Inter({ variable: "--font-inter", subsets: ["latin"] });
const instrument = Instrument_Sans({ variable: "--font-instrument", subsets: ["latin"], weight: ["500", "600", "700"] });

export const metadata: Metadata = {
  title: "TanyaDewan",
  description: "Tanya apa sahaja tentang perbahasan Dewan Rakyat. Setiap jawapan dipautkan ke Penyata Rasmi.",
};

// Set the saved (or system) theme before first paint so there's no light flash in dark mode.
const THEME_SCRIPT = `try{var t=localStorage.getItem("td_theme");document.documentElement.dataset.theme=t||(matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light")}catch(e){}`;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ms" data-theme="light" suppressHydrationWarning className={`${inter.variable} ${instrument.variable} h-full`}>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME_SCRIPT }} />
      </head>
      <body className="flex min-h-full flex-col">
        <TooltipProvider>
          <SiteHeader />
          <main className="flex-1">{children}</main>
          <footer className="border-t py-6 text-center text-[12px] text-subtle">
            <p className="mx-auto max-w-3xl px-4">
              Sumber: Penyata Rasmi Dewan Rakyat © Parlimen Malaysia. Setiap jawapan dipautkan ke PDF rasmi. TanyaDewan
              boleh tersilap: semak petikan dengan PDF.
            </p>
            <p className="mx-auto mt-2 max-w-3xl px-4">
              Dibina oleh{" "}
              <a
                href="https://github.com/edemocha"
                target="_blank"
                rel="noopener"
                className="font-medium text-muted-foreground underline-offset-2 hover:underline"
              >
                Danial Adam
              </a>
              {" · "}
              <a
                href="https://github.com/edemocha/tanyadewan"
                target="_blank"
                rel="noopener"
                className="underline-offset-2 hover:underline"
              >
                kod sumber
              </a>
            </p>
          </footer>
        </TooltipProvider>
      </body>
    </html>
  );
}
