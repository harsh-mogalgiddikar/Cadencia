import { Inbox, type LucideIcon } from "lucide-react";
import Link from "next/link";

interface Props {
  icon?: LucideIcon;
  title: string;
  description?: string;
  ctaLabel?: string;
  ctaHref?: string;
  onCtaClick?: () => void;
}

export default function EmptyState({
  icon: Icon = Inbox,
  title,
  description,
  ctaLabel,
  ctaHref,
  onCtaClick,
}: Props) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <div className="mb-4 rounded-xl bg-zinc-800 p-4">
        <Icon className="h-10 w-10 text-zinc-600" />
      </div>
      <p className="text-lg font-medium text-zinc-400">{title}</p>
      {description && (
        <p className="mt-1 max-w-md text-sm text-zinc-500">{description}</p>
      )}
      {ctaLabel && ctaHref && (
        <Link
          href={ctaHref}
          className="mt-4 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-emerald-600"
        >
          {ctaLabel}
        </Link>
      )}
      {ctaLabel && onCtaClick && !ctaHref && (
        <button
          onClick={onCtaClick}
          className="mt-4 rounded-lg bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black transition-colors hover:bg-emerald-600"
        >
          {ctaLabel}
        </button>
      )}
    </div>
  );
}
