import type { Metadata } from "next";
import { Toaster } from "sonner";
import "./globals.css";

export const metadata: Metadata = {
  title: "A2A Treasury Network — Autonomous B2B Trade on Algorand",
  description:
    "AI agents autonomously negotiate, escrow, and settle B2B trade deals on Algorand blockchain using the x402 payment protocol. Zero human intervention.",
  keywords: [
    "B2B trade",
    "Algorand",
    "AI agents",
    "autonomous commerce",
    "x402",
    "blockchain settlement",
    "DANP-v1",
  ],
  openGraph: {
    title: "A2A Treasury Network — Autonomous B2B Trade on Algorand",
    description:
      "AI agents autonomously negotiate and settle cross-border B2B trade deals on Algorand blockchain.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-zinc-950 text-zinc-50 antialiased">
        {/* Grid background */}
        <div
          className="grid-bg pointer-events-none fixed inset-0 z-0"
          aria-hidden="true"
        />

        {/* Content */}
        <div className="relative z-10">{children}</div>

        <Toaster
          position="bottom-right"
          theme="dark"
          richColors
          toastOptions={{
            style: {
              background: "#18181b",
              border: "1px solid #27272a",
              color: "#fafafa",
            },
          }}
        />
      </body>
    </html>
  );
}
