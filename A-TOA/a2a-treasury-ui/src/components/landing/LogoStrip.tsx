"use client";

const logos = [
  "Algorand",
  "Groq",
  "x402 Protocol",
  "DANP-v1",
  "FastAPI",
  "PostgreSQL",
  "Redis",
];

export default function LogoStrip() {
  return (
    <section className="relative overflow-hidden border-y border-zinc-800/50 bg-zinc-950 py-8">
      <div className="mb-4 text-center">
        <p className="text-xs font-medium uppercase tracking-widest text-zinc-500">
          Powered by
        </p>
      </div>

      {/* Marquee Container */}
      <div className="relative">
        {/* Left fade */}
        <div className="pointer-events-none absolute left-0 top-0 z-10 h-full w-24 bg-gradient-to-r from-zinc-950 to-transparent" />
        {/* Right fade */}
        <div className="pointer-events-none absolute right-0 top-0 z-10 h-full w-24 bg-gradient-to-l from-zinc-950 to-transparent" />

        <div className="flex animate-marquee gap-4">
          {/* Duplicate for seamless loop */}
          {[...logos, ...logos, ...logos, ...logos].map((logo, i) => (
            <div
              key={`${logo}-${i}`}
              className="flex shrink-0 items-center gap-2 rounded-full border border-zinc-800 bg-zinc-900 px-5 py-2.5 text-sm text-zinc-400 transition-colors hover:border-zinc-700 hover:text-zinc-300"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500/60" />
              {logo}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
