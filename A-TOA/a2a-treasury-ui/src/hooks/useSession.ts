"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import { getSessionStatus, getSessionOffers } from "@/lib/api";
import type { NegotiationSession, NegotiationRound } from "@/lib/types";

const TERMINAL_STATUSES = ["AGREED", "STALLED", "POLICY_BREACH"];

interface UseSessionReturn {
    session: NegotiationSession | null;
    rounds: NegotiationRound[];
    isLoading: boolean;
    isTerminal: boolean;
    error: string | null;
}

export function useSession(sessionId: string): UseSessionReturn {
    const [session, setSession] = useState<NegotiationSession | null>(null);
    const [rounds, setRounds] = useState<NegotiationRound[]>([]);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const isTerminalRef = useRef(false);
    const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

    const fetchStatus = useCallback(async () => {
        try {
            const res = await getSessionStatus(sessionId);
            const data = res.data as NegotiationSession;
            setSession(data);
            if (TERMINAL_STATUSES.includes(data.status)) {
                isTerminalRef.current = true;
            }
        } catch (err: unknown) {
            const msg =
                err instanceof Error ? err.message : "Failed to fetch session";
            setError(msg);
        }
    }, [sessionId]);

    const fetchOffers = useCallback(async () => {
        try {
            // Backend returns { session_id, offers: OfferDetail[] }
            const res = await getSessionOffers(sessionId);
            const data = res.data;
            const offers = data?.offers || data || [];
            if (!Array.isArray(offers)) return;

            // Map OfferDetail[] to NegotiationRound[]
            const parsed: NegotiationRound[] = offers.map(
                (offer: {
                    agent_role?: string;
                    action?: string;
                    value?: number;
                    offer_value?: number;
                    round?: number;
                    timestamp?: string;
                }) => ({
                    round_number: offer.round || 0,
                    actor: (offer.agent_role || "buyer") as "buyer" | "seller",
                    action: (offer.action || "counter").toUpperCase() as
                        | "COUNTER"
                        | "ACCEPT"
                        | "REJECT",
                    offer_amount: offer.value ?? offer.offer_value ?? 0,
                    timestamp: offer.timestamp || new Date().toISOString(),
                })
            );

            setRounds(parsed);
            setIsLoading(false);
        } catch {
            // Offers endpoint may not have data yet — non-critical
            setIsLoading(false);
        }
    }, [sessionId]);

    useEffect(() => {
        // Initial fetch
        fetchStatus();
        fetchOffers();

        // Polling
        intervalRef.current = setInterval(() => {
            if (isTerminalRef.current) {
                if (intervalRef.current) clearInterval(intervalRef.current);
                // One final fetch
                fetchOffers();
                return;
            }
            fetchStatus();
            fetchOffers();
        }, 1500);

        return () => {
            if (intervalRef.current) clearInterval(intervalRef.current);
        };
    }, [fetchStatus, fetchOffers]);

    return {
        session,
        rounds,
        isLoading,
        isTerminal:
            isTerminalRef.current ||
            TERMINAL_STATUSES.includes(session?.status ?? ""),
        error,
    };
}
