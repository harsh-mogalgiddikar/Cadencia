"use client";

import { cn } from "@/lib/utils";

interface StatusBadgeProps {
    status: string;
    size?: "sm" | "md";
    pulse?: boolean;
}

const colorMap: Record<string, string> = {
    AGREED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    CONFIRMED: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    ACTIVE: "bg-indigo-500/20 text-indigo-400 border-indigo-500/30",
    PENDING: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    AWAITING_PAYMENT: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    POLICY_BREACH: "bg-red-500/20 text-red-400 border-red-500/30",
    STALLED: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    active: "bg-emerald-500/20 text-emerald-400 border-emerald-500/30",
    busy: "bg-amber-500/20 text-amber-400 border-amber-500/30",
    inactive: "bg-gray-500/20 text-gray-400 border-gray-500/30",
    buyer: "bg-blue-500/20 text-blue-400 border-blue-500/30",
    seller: "bg-purple-500/20 text-purple-400 border-purple-500/30",
};

const pulseStatuses = new Set(["ACTIVE", "PENDING", "active"]);

export default function StatusBadge({ status, size = "sm", pulse }: StatusBadgeProps) {
    const colors = colorMap[status] || "bg-gray-500/20 text-gray-400 border-gray-500/30";
    const shouldPulse = pulse ?? pulseStatuses.has(status);

    return (
        <span
            className={cn(
                "inline-flex items-center gap-1.5 rounded-full border font-medium",
                colors,
                size === "sm" ? "px-2.5 py-0.5 text-xs" : "px-3 py-1 text-sm"
            )}
        >
            {shouldPulse && (
                <span className="relative flex h-2 w-2">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-current opacity-60" />
                    <span className="relative inline-flex h-2 w-2 rounded-full bg-current" />
                </span>
            )}
            {status}
        </span>
    );
}
