"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

interface Props {
  text: string;
  truncate?: number;
  className?: string;
  mono?: boolean;
}

export default function CopyButton({
  text,
  truncate,
  className = "",
  mono = true,
}: Props) {
  const [copied, setCopied] = useState(false);

  const display = truncate
    ? text.length > truncate
      ? `${text.slice(0, truncate / 2)}...${text.slice(-truncate / 2)}`
      : text
    : text;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <button
      onClick={handleCopy}
      className={`inline-flex items-center gap-1.5 rounded px-1 py-0.5 text-left transition-colors hover:bg-zinc-800 ${className}`}
      title={text}
    >
      <span className={mono ? "font-mono text-xs text-cyan-400" : ""}>
        {display}
      </span>
      {copied ? (
        <Check className="h-3 w-3 shrink-0 text-emerald-500" />
      ) : (
        <Copy className="h-3 w-3 shrink-0 text-zinc-500" />
      )}
    </button>
  );
}
