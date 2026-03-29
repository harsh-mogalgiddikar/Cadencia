/** Format INR with Indian number system */
export const formatINR = (amount: number): string =>
    new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency: "INR",
        maximumFractionDigits: 0,
    }).format(amount);

/** Truncate blockchain address/hash for display */
export const truncateHash = (hash: string, chars = 8): string =>
    hash ? `${hash.slice(0, chars)}...` : "";

/** Build Algorand explorer URL for a transaction */
export const explorerTxUrl = (txId: string): string =>
    `${process.env.NEXT_PUBLIC_EXPLORER_BASE}/transaction/${txId}`;

/** Build Algorand explorer URL for an account */
export const explorerAccountUrl = (address: string): string =>
    `${process.env.NEXT_PUBLIC_EXPLORER_BASE}/account/${address}`;

/** Session status → Tailwind text color class */
export const statusColor = (status: string): string =>
    ({
        AGREED: "text-emerald-400",
        CONFIRMED: "text-emerald-400",
        ACTIVE: "text-indigo-400",
        PENDING: "text-amber-400",
        AWAITING_PAYMENT: "text-amber-400",
        POLICY_BREACH: "text-red-400",
        STALLED: "text-gray-400",
    })[status] ?? "text-gray-400";

/** Relative time string */
export const timeAgo = (dateStr: string): string => {
    const diff = Date.now() - new Date(dateStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
};

/** cn helper for merging classnames */
export function cn(...classes: (string | undefined | false | null)[]): string {
    return classes.filter(Boolean).join(" ");
}

/**
 * Extract a human-readable error message from an API error response.
 * Handles:
 *  - FastAPI 422 validation errors: { detail: [{type, loc, msg, input, ctx}] }
 *  - Standard errors: { detail: "some string" }
 *  - Fallback to generic message
 */
export function extractApiError(err: unknown, fallback = "Something went wrong"): string {
    const resp = (err as { response?: { data?: { detail?: unknown } } })?.response?.data;
    if (!resp?.detail) return fallback;

    const detail = resp.detail;

    // FastAPI string detail
    if (typeof detail === "string") return detail;

    // FastAPI 422: detail is array of validation errors
    if (Array.isArray(detail)) {
        return detail
            .map((e: { msg?: string; loc?: (string | number)[] }) => {
                const field = e.loc?.slice(-1)?.[0] || "";
                return field ? `${field}: ${e.msg}` : (e.msg || "");
            })
            .filter(Boolean)
            .join("; ") || fallback;
    }

    return fallback;
}
