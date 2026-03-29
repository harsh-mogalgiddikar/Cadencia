"use client";

import { useState, useEffect, useCallback } from "react";
import { getAuditLog, getMerkleRoot, verifyChain } from "@/lib/api";
import type { AuditEntry, MerkleData } from "@/lib/types";

interface UseAuditReturn {
    entries: AuditEntry[];
    merkle: MerkleData | null;
    chainValid: boolean | null;
    isLoading: boolean;
    error: string | null;
}

export function useAudit(sessionId: string): UseAuditReturn {
    const [entries, setEntries] = useState<AuditEntry[]>([]);
    const [merkle, setMerkle] = useState<MerkleData | null>(null);
    const [chainValid, setChainValid] = useState<boolean | null>(null);
    const [isLoading, setIsLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const fetchAudit = useCallback(async () => {
        try {
            setIsLoading(true);
            const [logRes, chainRes] = await Promise.all([
                getAuditLog(sessionId),
                verifyChain(),
            ]);

            const logEntries = logRes.data?.entries || logRes.data || [];
            setEntries(Array.isArray(logEntries) ? logEntries : []);
            setChainValid(chainRes.data?.valid ?? chainRes.data?.chain_valid ?? null);
        } catch (err: unknown) {
            const msg =
                err instanceof Error ? err.message : "Failed to fetch audit data";
            setError(msg);
        } finally {
            setIsLoading(false);
        }
    }, [sessionId]);

    const fetchMerkle = useCallback(async () => {
        // Poll for merkle up to 12 seconds with 2s intervals
        let attempts = 0;
        const maxAttempts = 6;

        const poll = async () => {
            try {
                const res = await getMerkleRoot(sessionId);
                const data = res.data as MerkleData;
                setMerkle(data);

                if (!data.anchored_on_chain && attempts < maxAttempts) {
                    attempts++;
                    setTimeout(poll, 2000);
                }
            } catch {
                if (attempts < maxAttempts) {
                    attempts++;
                    setTimeout(poll, 2000);
                }
            }
        };

        poll();
    }, [sessionId]);

    useEffect(() => {
        fetchAudit();
        fetchMerkle();
    }, [fetchAudit, fetchMerkle]);

    return { entries, merkle, chainValid, isLoading, error };
}
