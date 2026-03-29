import { AlertCircle, RefreshCw } from "lucide-react";

interface Props {
  error: unknown;
  onRetry?: () => void;
}

export default function ApiError({ error, onRetry }: Props) {
  const msg =
    error && typeof error === "object" && "error" in error
      ? String((error as Record<string, unknown>).error)
      : error && typeof error === "object" && "detail" in error
      ? String((error as Record<string, unknown>).detail)
      : "Failed to load data";

  return (
    <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-500/10 px-4 py-3">
      <AlertCircle className="mt-0.5 h-5 w-5 shrink-0 text-red-400" />
      <div className="flex-1">
        <p className="text-sm text-red-400">{msg}</p>
      </div>
      {onRetry && (
        <button
          onClick={onRetry}
          className="flex items-center gap-1.5 rounded-lg border border-red-500/30 px-3 py-1.5 text-xs font-medium text-red-400 transition-colors hover:bg-red-500/10"
        >
          <RefreshCw className="h-3 w-3" />
          Retry
        </button>
      )}
    </div>
  );
}
