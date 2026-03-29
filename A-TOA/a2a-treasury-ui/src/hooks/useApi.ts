"use client";

import useSWR, { type SWRConfiguration } from "swr";
import type { SessionStatus, AgentConfig } from "@/types/api";

// ── Generic fetcher ────────────────────────────────────────
const fetcher = async (url: string) => {
  const res = await fetch(url, { credentials: "include" });
  if (res.status === 401) {
    window.location.href = "/auth/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw err;
  }
  return res.json();
};

// Fetcher that returns null on 404 instead of throwing
// (used for resources that may not exist yet, like agent config)
const fetcher404Null = async (url: string) => {
  const res = await fetch(url, { credentials: "include" });
  if (res.status === 401) {
    window.location.href = "/auth/login";
    throw new Error("Unauthorized");
  }
  if (res.status === 404) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw err;
  }
  return res.json();
};

function useApi<T>(
  key: string | null,
  config?: SWRConfiguration,
) {
  return useSWR<T>(key, fetcher, config);
}

// ── Treasury / Platform ────────────────────────────────────
export const usePlatformSummary = () =>
  useApi("/api/v1/treasury/platform", { refreshInterval: 10_000 });

export const useEnterpriseSummary = (id: string | undefined) =>
  useApi(id ? `/api/v1/treasury/${id}` : null, { refreshInterval: 10_000 });

// ── Sessions ───────────────────────────────────────────────
export const useSessions = (status?: string) => {
  const q = status ? `?status=${status}` : "";
  return useApi(`/api/v1/sessions/${q}`, { refreshInterval: 5_000 });
};

export const useSessionStatus = (id: string | undefined) =>
  useSWR<SessionStatus>(
    id ? `/api/v1/sessions/${id}/status` : null,
    fetcher,
    {
      refreshInterval: (data?: SessionStatus) =>
        data && data.is_terminal ? 0 : 2_000,
    },
  );

export const useSessionOffers = (id: string | undefined) =>
  useApi(id ? `/api/v1/sessions/${id}/offers` : null, {
    refreshInterval: 2_000,
  });

export const useSessionTranscript = (id: string | undefined) =>
  useApi(id ? `/api/v1/sessions/${id}/transcript` : null, {
    refreshInterval: 3_000,
  });

// ── Escrow ─────────────────────────────────────────────────
export const useEscrowBySession = (sessionId: string | undefined) =>
  useApi(sessionId ? `/api/v1/escrow/session/${sessionId}` : null);

export const useEscrowStatus = (escrowId: string | undefined) =>
  useApi(escrowId ? `/api/v1/escrow/${escrowId}/status` : null);

// ── Audit ──────────────────────────────────────────────────
export const useAuditLog = (enterpriseId: string | undefined) =>
  useApi(enterpriseId ? `/api/v1/audit/${enterpriseId}/log` : null);

export const useMerkleRoot = (sessionId: string | undefined) =>
  useApi(sessionId ? `/api/v1/audit/${sessionId}/merkle` : null);

// ── Compliance ─────────────────────────────────────────────
export const useComplianceHistory = (enterpriseId: string | undefined) =>
  useApi(
    enterpriseId ? `/api/v1/compliance/${enterpriseId}/history` : null,
    { refreshInterval: 15_000 },
  );

export const useSessionCompliance = (sessionId: string | undefined) =>
  useApi(sessionId ? `/api/v1/compliance/session/${sessionId}` : null);

// ── FX ─────────────────────────────────────────────────────
export const useFxRate = () =>
  useApi("/api/v1/fx/rate", { refreshInterval: 30_000 });

// ── Registry ───────────────────────────────────────────────
export const useAgentRegistry = (service?: string, protocol?: string) => {
  const params = new URLSearchParams();
  if (service) params.set("service", service);
  if (protocol) params.set("protocol", protocol);
  const q = params.toString();
  return useApi(q ? `/api/v1/agents?${q}` : "/api/v1/agents");
};

// ── Agent Config ───────────────────────────────────────────
export const useAgentConfig = (enterpriseId: string | undefined) =>
  useSWR<AgentConfig | null>(
    enterpriseId ? `/api/v1/enterprises/${enterpriseId}/agent-config` : null,
    fetcher404Null,
  );

// ── Generic POST helper (for mutations) ────────────────────
export async function apiPost<T = unknown>(
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(`/api/v1${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined,
  });
  if (res.status === 401) {
    window.location.href = "/auth/login";
    throw new Error("Unauthorized");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw err;
  }
  return res.json();
}
