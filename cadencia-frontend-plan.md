# Cadencia — Frontend Implementation Plan

> **Project**: Cadencia — B2B Agentic Commerce Marketplace  
> **Version**: 1.0.0  
> **Date**: 2026-03-31  
> **Stack**: Next.js 16 · React 19 · TypeScript 5.x · TailwindCSS 4 · Zustand · SWR  
> **Alignment**: Backend Implementation Plan v1.0 (7-Phase)  

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Application Pages & Screen Map](#2-application-pages--screen-map)
3. [Directory Structure](#3-directory-structure)
4. [Component Architecture](#4-component-architecture)
5. [State Management & Data Flow](#5-state-management--data-flow)
6. [Phase 1 — Blockchain Visibility Layer](#6-phase-1--blockchain-visibility-layer)
7. [Phase 2 — Escrow Lifecycle UI](#7-phase-2--escrow-lifecycle-ui)
8. [Phase 3 — Payment & Settlement UI](#8-phase-3--payment--settlement-ui)
9. [Phase 4 — Rebrand, Cleanup & Multi-Tenancy](#9-phase-4--rebrand-cleanup--multi-tenancy)
10. [Phase 5 — Marketplace Discovery UI](#10-phase-5--marketplace-discovery-ui)
11. [Phase 6 — API Hardening & Auth Overhaul](#11-phase-6--api-hardening--auth-overhaul)
12. [Phase 7 — Deployment & Production Readiness](#12-phase-7--deployment--production-readiness)
13. [Complete API Integration Map](#13-complete-api-integration-map)
14. [Error Handling Strategy](#14-error-handling-strategy)
15. [Testing Strategy](#15-testing-strategy)

---

## 1. Architecture Overview

### 1.1 Technology Decisions

| Layer | Technology | Reason |
|---|---|---|
| Framework | Next.js 16 (App Router) | Existing project; SSR, API routes, middleware |
| Language | TypeScript 5.x (strict mode) | Type safety across API boundaries |
| Styling | TailwindCSS 4 + CSS variables | Existing project; rapid iteration, theme support |
| State (global) | Zustand | Lightweight, no boilerplate, works with SSR |
| State (server) | SWR 2.x | Already in project; cache-first data fetching with revalidation |
| Animations | Framer Motion 12 | Already in project; page transitions, negotiation feed |
| Icons | Lucide React | Already in project; consistent icon set |
| Tables | @tanstack/react-table 8 | Already in project; session/escrow/audit lists |
| Toasts | Sonner | Already in project; non-blocking notifications |
| Forms | React Hook Form + Zod | Type-safe validation matching backend Pydantic schemas |
| Charts | Recharts | Treasury analytics dashboard |
| Real-time | EventSource (native SSE) | Auto-negotiate streaming |

### 1.2 Design System Tokens

All UI components consume these CSS variables for consistent theming and the Cadencia rebrand:

```css
:root {
  /* Brand */
  --cad-primary: #6366f1;       /* Indigo-500 — primary actions */
  --cad-primary-hover: #4f46e5; /* Indigo-600 */
  --cad-secondary: #0ea5e9;    /* Sky-500 — blockchain/Algorand accent */
  --cad-success: #22c55e;       /* Green-500 — AGREED, RELEASED, COMPLIANT */
  --cad-warning: #f59e0b;       /* Amber-500 — WARNING, PENDING */
  --cad-danger: #ef4444;        /* Red-500 — WALKAWAY, REFUNDED, NON_COMPLIANT */
  --cad-neutral: #64748b;       /* Slate-500 — secondary text */

  /* Surfaces */
  --cad-bg: #0f172a;            /* Slate-900 — dark mode default */
  --cad-surface: #1e293b;       /* Slate-800 — cards */
  --cad-surface-hover: #334155; /* Slate-700 */
  --cad-border: #334155;        /* Slate-700 */

  /* Typography */
  --cad-text: #f8fafc;          /* Slate-50 */
  --cad-text-muted: #94a3b8;   /* Slate-400 */
  --cad-font-sans: 'Inter', system-ui, sans-serif;
  --cad-font-mono: 'JetBrains Mono', monospace;
}
```

### 1.3 User Roles

| Role | Access | Description |
|---|---|---|
| **admin** | Full | Enterprise owner. Manages config, agents, escrow, compliance. |
| **auditor** | Read-only | Views audit trails, compliance records, session history. |
| **unauthenticated** | Landing, auth, pricing | Public pages only. |

---

## 2. Application Pages & Screen Map

### 2.1 Complete Page Inventory

The application has **17 pages** organized into 4 zones:

#### Zone 1 — Public (No Auth)

| # | Route | Page Name | Purpose |
|---|---|---|---|
| 1 | `/` | Landing Page | Product showcase, features, pricing teaser, CTA |
| 2 | `/auth/login` | Login | Enterprise user authentication |
| 3 | `/register` | Registration | Enterprise + user account creation |
| 4 | `/pricing` | Pricing | SaaS plan comparison (informational) |

#### Zone 2 — Dashboard (Auth Required — admin + auditor)

| # | Route | Page Name | Purpose |
|---|---|---|---|
| 5 | `/dashboard` | Dashboard Home | Overview metrics, recent sessions, quick actions |
| 6 | `/dashboard/sessions` | Sessions List | All negotiation sessions with filtering and search |
| 7 | `/dashboard/sessions/[id]` | Session Detail | Full session view: rounds, offers, FSM state, escrow |
| 8 | `/dashboard/escrow` | Escrow Management | All escrow contracts, lifecycle status, actions |
| 9 | `/dashboard/escrow/[id]` | Escrow Detail | Single escrow: fund/release/refund actions, tx links |
| 10 | `/dashboard/audit` | Audit Trail | Hash-chain viewer, Merkle verification, anchors |
| 11 | `/dashboard/compliance` | Compliance Records | FEMA check history, status badges |
| 12 | `/dashboard/settings` | Settings | Agent config, enterprise profile, API keys |

#### Zone 3 — Marketplace (Auth Required — admin only)

| # | Route | Page Name | Purpose |
|---|---|---|---|
| 13 | `/marketplace` | Marketplace Search | Discover counterparties, search, filter, match scores |
| 14 | `/marketplace/initiate/[id]` | Initiate Trade | Pre-negotiation: review counterparty, configure terms, handshake |

#### Zone 4 — Active Operations (Auth Required — admin only)

| # | Route | Page Name | Purpose |
|---|---|---|---|
| 15 | `/negotiate/[id]` | Live Negotiation | Real-time negotiation view with SSE streaming |
| 16 | `/settlement/[id]` | Settlement View | x402 payment flow, delivery status |
| 17 | `/treasury` | Treasury Analytics | Portfolio analytics, charts, compliance summary |

### 2.2 Navigation Structure

```
┌────────────────────────────────────────────────────────────┐
│  Top Bar: Cadencia logo · Enterprise name · Role badge     │
│           · Notifications bell · Profile dropdown          │
├────────────────┬───────────────────────────────────────────┤
│                │                                           │
│  Sidebar       │  Main Content Area                       │
│  ────────      │                                           │
│  Dashboard     │  [Active Page]                           │
│  Sessions      │                                           │
│  Marketplace   │                                           │
│  Escrow        │                                           │
│  Treasury      │                                           │
│  Audit         │                                           │
│  Compliance    │                                           │
│  ────────      │                                           │
│  Settings      │                                           │
│                │                                           │
└────────────────┴───────────────────────────────────────────┘
```

Sidebar items visible per role:

| Item | admin | auditor |
|---|---|---|
| Dashboard | ✅ | ✅ |
| Sessions | ✅ | ✅ |
| Marketplace | ✅ | ❌ |
| Escrow | ✅ | ✅ (read-only) |
| Treasury | ✅ | ✅ |
| Audit | ✅ | ✅ |
| Compliance | ✅ | ✅ |
| Settings | ✅ | ❌ |

---

## 3. Directory Structure

```
a2a-treasury-ui/
├── src/
│   ├── app/                              # Next.js App Router
│   │   ├── layout.tsx                    # Root layout (providers, fonts)
│   │   ├── page.tsx                      # Landing page (/)
│   │   ├── auth/
│   │   │   └── login/
│   │   │       └── page.tsx              # Login page
│   │   ├── register/
│   │   │   └── page.tsx                  # Registration page
│   │   ├── pricing/
│   │   │   └── page.tsx                  # Pricing page
│   │   ├── dashboard/
│   │   │   ├── layout.tsx                # Dashboard shell (sidebar + topbar)
│   │   │   ├── page.tsx                  # Dashboard home
│   │   │   ├── sessions/
│   │   │   │   ├── page.tsx              # Sessions list
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx          # Session detail
│   │   │   ├── escrow/
│   │   │   │   ├── page.tsx              # Escrow list
│   │   │   │   └── [id]/
│   │   │   │       └── page.tsx          # Escrow detail
│   │   │   ├── audit/
│   │   │   │   └── page.tsx              # Audit trail
│   │   │   ├── compliance/
│   │   │   │   └── page.tsx              # Compliance records
│   │   │   └── settings/
│   │   │       └── page.tsx              # Settings (agent config, API keys)
│   │   ├── marketplace/
│   │   │   ├── page.tsx                  # Marketplace search
│   │   │   └── initiate/
│   │   │       └── [id]/
│   │   │           └── page.tsx          # Initiate trade
│   │   ├── negotiate/
│   │   │   └── [id]/
│   │   │       └── page.tsx              # Live negotiation
│   │   ├── settlement/
│   │   │   └── [id]/
│   │   │       └── page.tsx              # Settlement view
│   │   └── treasury/
│   │       └── page.tsx                  # Treasury analytics
│   │
│   ├── components/                       # Reusable UI components
│   │   ├── layout/                       # Layout components
│   │   │   ├── Sidebar.tsx
│   │   │   ├── TopBar.tsx
│   │   │   ├── DashboardShell.tsx
│   │   │   └── PublicNav.tsx
│   │   ├── landing/                      # Landing page sections (existing)
│   │   │   ├── HeroSection.tsx
│   │   │   ├── FeaturesGrid.tsx
│   │   │   ├── HowItWorks.tsx
│   │   │   ├── StatsSection.tsx
│   │   │   ├── LiveDemoSection.tsx
│   │   │   ├── PricingCards.tsx
│   │   │   ├── PricingTeaser.tsx
│   │   │   ├── LogoStrip.tsx
│   │   │   └── CTABanner.tsx
│   │   ├── auth/                         # Auth components
│   │   │   ├── LoginForm.tsx
│   │   │   ├── RegisterForm.tsx
│   │   │   └── KYCVerificationForm.tsx
│   │   ├── dashboard/                    # Dashboard widgets
│   │   │   ├── MetricsGrid.tsx
│   │   │   ├── RecentSessionsTable.tsx
│   │   │   ├── QuickActions.tsx
│   │   │   └── NewSessionModal.tsx
│   │   ├── sessions/                     # Session components
│   │   │   ├── SessionsTable.tsx
│   │   │   ├── SessionDetail.tsx
│   │   │   ├── OffersTimeline.tsx
│   │   │   ├── FSMStateIndicator.tsx
│   │   │   └── SessionFilters.tsx
│   │   ├── negotiation/                  # Negotiation components
│   │   │   ├── NegotiationFeed.tsx
│   │   │   ├── OfferCard.tsx
│   │   │   ├── RoundCounter.tsx
│   │   │   ├── SSEStreamHandler.tsx
│   │   │   └── NegotiationControls.tsx
│   │   ├── escrow/                       # Escrow components
│   │   │   ├── EscrowTable.tsx
│   │   │   ├── EscrowDetail.tsx
│   │   │   ├── EscrowLifecycle.tsx
│   │   │   ├── FundEscrowModal.tsx
│   │   │   ├── ReleaseEscrowModal.tsx
│   │   │   ├── RefundEscrowModal.tsx
│   │   │   └── AlgorandTxLink.tsx
│   │   ├── marketplace/                  # Marketplace components
│   │   │   ├── MarketplaceGrid.tsx
│   │   │   ├── CounterpartyCard.tsx
│   │   │   ├── SearchFilters.tsx
│   │   │   ├── MatchScoreBadge.tsx
│   │   │   ├── InitiateTradeForm.tsx
│   │   │   └── HandshakeResult.tsx
│   │   ├── audit/                        # Audit components
│   │   │   ├── AuditTrailViewer.tsx
│   │   │   ├── HashChainRow.tsx
│   │   │   ├── MerkleProofPanel.tsx
│   │   │   └── AnchorVerification.tsx
│   │   ├── compliance/                   # Compliance components
│   │   │   ├── ComplianceTable.tsx
│   │   │   └── FEMACheckResult.tsx
│   │   ├── treasury/                     # Treasury components
│   │   │   ├── PortfolioMetrics.tsx
│   │   │   ├── SessionChart.tsx
│   │   │   ├── EscrowValueChart.tsx
│   │   │   └── ComplianceSummary.tsx
│   │   ├── settlement/                   # Settlement components
│   │   │   ├── X402PaymentFlow.tsx
│   │   │   ├── PaymentRequirement.tsx
│   │   │   └── DeliveryStatus.tsx
│   │   ├── settings/                     # Settings components
│   │   │   ├── AgentConfigForm.tsx
│   │   │   ├── EnterpriseProfile.tsx
│   │   │   └── APIKeyManager.tsx
│   │   └── ui/                           # Generic primitives
│   │       ├── Button.tsx
│   │       ├── Input.tsx
│   │       ├── Select.tsx
│   │       ├── Modal.tsx
│   │       ├── Card.tsx
│   │       ├── Badge.tsx
│   │       ├── StatusBadge.tsx
│   │       ├── Skeleton.tsx
│   │       ├── EmptyState.tsx
│   │       ├── ErrorBanner.tsx
│   │       ├── ConfirmDialog.tsx
│   │       ├── CopyButton.tsx
│   │       ├── DataTable.tsx
│   │       ├── Pagination.tsx
│   │       └── Tooltip.tsx
│   │
│   ├── services/                         # API layer
│   │   ├── api-client.ts                 # Axios instance, interceptors, base config
│   │   ├── auth.service.ts               # /v1/auth/* endpoints
│   │   ├── enterprise.service.ts         # /v1/enterprises/* endpoints
│   │   ├── session.service.ts            # /v1/sessions/* endpoints
│   │   ├── escrow.service.ts             # /v1/escrow/* endpoints
│   │   ├── marketplace.service.ts        # /v1/marketplace/* endpoints
│   │   ├── audit.service.ts              # /v1/audit/* endpoints
│   │   ├── compliance.service.ts         # /v1/compliance/* endpoints
│   │   ├── treasury.service.ts           # /v1/treasury/* endpoints
│   │   ├── fx.service.ts                 # /v1/fx/* endpoints
│   │   ├── settlement.service.ts         # /v1/deliver/* endpoints
│   │   ├── framework.service.ts          # /v1/framework/* endpoints
│   │   └── handshake.service.ts          # /v1/handshake/* endpoints
│   │
│   ├── stores/                           # Zustand state stores
│   │   ├── auth.store.ts                 # Auth state (token, user, enterprise)
│   │   ├── session.store.ts              # Active negotiation state
│   │   ├── escrow.store.ts               # Escrow transaction state
│   │   └── notification.store.ts         # Toast/notification queue
│   │
│   ├── hooks/                            # Custom React hooks
│   │   ├── useAuth.ts                    # Auth actions + state
│   │   ├── useSession.ts                 # Session data + polling
│   │   ├── useEscrow.ts                  # Escrow data + actions
│   │   ├── useMarketplace.ts             # Marketplace search + initiate
│   │   ├── useAudit.ts                   # Audit trail data
│   │   ├── useSSE.ts                     # Server-Sent Events connection
│   │   ├── useTreasury.ts               # Treasury analytics data
│   │   ├── useDebounce.ts               # Input debouncing
│   │   └── useAlgorandExplorer.ts       # Algorand tx/app link generation
│   │
│   ├── lib/                              # Utilities
│   │   ├── api.ts                        # Legacy API client (deprecate → services/)
│   │   ├── auth.ts                       # Token get/set/clear helpers
│   │   ├── auth-context.tsx              # DEPRECATED → use auth.store.ts
│   │   ├── animations.ts                 # Framer Motion variants
│   │   ├── constants.ts                  # Status maps, role maps, route maps
│   │   ├── formatters.ts                 # Currency, date, address formatting
│   │   ├── validators.ts                 # Zod schemas (mirror backend Pydantic)
│   │   └── utils.ts                      # General utilities
│   │
│   └── types/                            # TypeScript types
│       ├── api.ts                        # API response types (existing, extend)
│       ├── auth.types.ts                 # Auth-specific types
│       ├── session.types.ts              # Session/negotiation types
│       ├── escrow.types.ts               # Escrow types
│       ├── marketplace.types.ts          # Marketplace types
│       ├── audit.types.ts                # Audit types
│       ├── compliance.types.ts           # Compliance types
│       ├── treasury.types.ts             # Treasury types
│       └── algorand.types.ts             # Blockchain transaction types
│
├── middleware.ts                          # Auth guard (existing, refactor)
├── next.config.ts                        # Next.js configuration
├── tailwind.config.ts                    # Tailwind + CSS variable theme
├── tsconfig.json                         # Strict TypeScript config
├── .env.local                            # Dev environment
├── .env.production                       # Production environment
└── package.json
```

---

## 4. Component Architecture

### 4.1 Layout Components

#### `DashboardShell` — The Master Layout

Used by all `/dashboard/*`, `/marketplace/*`, `/negotiate/*`, `/settlement/*`, `/treasury` routes.

```
┌──────────────────────────────────────────────────────────────┐
│  TopBar                                                      │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Logo  ·  Enterprise: Bharat Steel Corp  ·  [admin]  · 🔔│ │
│  └─────────────────────────────────────────────────────────┘ │
├──────────────┬───────────────────────────────────────────────┤
│              │                                               │
│  Sidebar     │  {children}                                  │
│  ┌────────┐  │                                               │
│  │ 📊 Dash │  │                                               │
│  │ 📋 Sess │  │                                               │
│  │ 🏪 Mkt  │  │                                               │
│  │ 🔒 Escr │  │                                               │
│  │ 💰 Treas│  │                                               │
│  │ 📜 Audit│  │                                               │
│  │ ✅ Comp │  │                                               │
│  │ ⚙ Sett │  │                                               │
│  └────────┘  │                                               │
└──────────────┴───────────────────────────────────────────────┘
```

**Props:** None (reads from auth store for role-based sidebar filtering)

**State consumed:**
- `auth.store` → enterprise name, role, user info
- `notification.store` → unread count for bell icon

#### `TopBar`

```typescript
// components/layout/TopBar.tsx
interface TopBarProps {
  enterprise: { legal_name: string; kyc_status: string };
  user: { email: string; role: "admin" | "auditor" };
}
```

**Functionality:**
- Displays Cadencia logo (left)
- Enterprise name + KYC status badge (center)
- Notification bell + profile dropdown (right)
- Profile dropdown: Settings link, Logout action

#### `Sidebar`

```typescript
// components/layout/Sidebar.tsx
// Reads role from auth store, filters menu items accordingly
// Highlights active route using usePathname()
// Collapsible on mobile (hamburger menu)
```

### 4.2 UI Primitives

These are the atomic building blocks used across all pages. Each is a controlled component with consistent API:

#### `StatusBadge`

The most-used component in the app. Maps backend status strings to colored badges:

```typescript
// components/ui/StatusBadge.tsx
interface StatusBadgeProps {
  status: string;
  size?: "sm" | "md" | "lg";
}

const STATUS_MAP: Record<string, { color: string; label: string }> = {
  // Session statuses
  INIT:           { color: "bg-slate-500",   label: "Initialized" },
  BUYER_ANCHOR:   { color: "bg-blue-500",    label: "Buyer Anchored" },
  SELLER_RESPONSE:{ color: "bg-blue-500",    label: "Seller Turn" },
  ROUND_LOOP:     { color: "bg-indigo-500",  label: "Negotiating" },
  AGREED:         { color: "bg-green-500",    label: "Agreed" },
  WALKAWAY:       { color: "bg-red-500",      label: "Walkaway" },
  TIMEOUT:        { color: "bg-amber-500",    label: "Timeout" },
  ROUND_LIMIT:    { color: "bg-amber-500",    label: "Round Limit" },
  STALLED:        { color: "bg-amber-500",    label: "Stalled" },
  POLICY_BREACH:  { color: "bg-red-500",      label: "Policy Breach" },
  // Escrow statuses
  DEPLOYED:       { color: "bg-blue-500",     label: "Deployed" },
  FUNDED:         { color: "bg-indigo-500",   label: "Funded" },
  RELEASED:       { color: "bg-green-500",    label: "Released" },
  REFUNDED:       { color: "bg-amber-500",    label: "Refunded" },
  // KYC statuses
  PENDING:        { color: "bg-amber-500",    label: "Pending" },
  ACTIVE:         { color: "bg-green-500",    label: "Active" },
  // Compliance statuses
  COMPLIANT:      { color: "bg-green-500",    label: "Compliant" },
  WARNING:        { color: "bg-amber-500",    label: "Warning" },
  NON_COMPLIANT:  { color: "bg-red-500",      label: "Non-Compliant" },
  EXEMPT:         { color: "bg-slate-500",    label: "Exempt" },
};
```

#### `AlgorandTxLink`

Links to Algorand explorer for transaction and application IDs:

```typescript
// components/escrow/AlgorandTxLink.tsx
interface AlgorandTxLinkProps {
  txId?: string;
  appId?: number;
  network?: "testnet" | "mainnet";
  truncate?: boolean;
}

// Renders: https://testnet.explorer.perawallet.app/tx/{txId}
// or: https://testnet.explorer.perawallet.app/application/{appId}
```

#### `DataTable`

Generic sortable, filterable table powered by @tanstack/react-table:

```typescript
// components/ui/DataTable.tsx
interface DataTableProps<T> {
  data: T[];
  columns: ColumnDef<T>[];
  loading?: boolean;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  pagination?: { page: number; limit: number; total: number };
  onPageChange?: (page: number) => void;
}
```

Used by: SessionsTable, EscrowTable, ComplianceTable, AuditTrailViewer.

### 4.3 Feature Components

#### `NegotiationFeed` — Real-Time Offer Stream

```typescript
// components/negotiation/NegotiationFeed.tsx
interface NegotiationFeedProps {
  sessionId: string;
  initialOffers: Offer[];
  streaming: boolean;  // true during auto-negotiate
}
```

**Behavior:**
- Renders chronological list of `OfferCard` components
- During auto-negotiate: connects to SSE endpoint, appends offers in real-time
- Each offer shows: round, agent role (buyer/seller), action, value, confidence bar, strategy tag, rationale
- Animates new offers with Framer Motion `AnimatePresence`
- Auto-scrolls to latest offer

#### `EscrowLifecycle` — Visual State Machine

```typescript
// components/escrow/EscrowLifecycle.tsx
interface EscrowLifecycleProps {
  escrow: EscrowData;
}
```

**Renders a horizontal pipeline:**
```
[DEPLOYED] ──→ [FUNDED] ──→ [RELEASED]
                  │
                  └──→ [REFUNDED]
```

Active step highlighted, completed steps green, future steps dimmed. Each step shows its `tx_id` as an `AlgorandTxLink`.

#### `MerkleProofPanel` — Audit Verification

```typescript
// components/audit/MerkleProofPanel.tsx
interface MerkleProofPanelProps {
  sessionId: string;
  merkleRoot: string;
  anchorTxId?: string;
}
```

**Functionality:**
- Fetches Merkle proof from `GET /v1/audit/{session_id}/merkle`
- Displays tree visualization (root, leaf count)
- "Verify on-chain" button: links to Algorand explorer for anchor tx
- "Verify proof" action: calls `POST /v1/audit/verify` and shows pass/fail

---

## 5. State Management & Data Flow

### 5.1 Global State (Zustand)

Four stores handle application-wide state:

#### `auth.store.ts`

```typescript
interface AuthState {
  token: string | null;
  user: { user_id: string; email: string; role: "admin" | "auditor" } | null;
  enterprise: {
    enterprise_id: string;
    legal_name: string;
    kyc_status: string;
    trade_role: string;
  } | null;
  isAuthenticated: boolean;

  // Actions
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
  refresh: () => Promise<void>;
  hydrate: () => void; // Load from cookie on mount
}
```

**Persistence:** JWT stored in `a2a_token` httpOnly cookie (set by login, cleared by logout). Enterprise data cached in Zustand and rehydrated from cookie on page load.

#### `session.store.ts`

```typescript
interface SessionState {
  activeSessionId: string | null;
  sseConnection: EventSource | null;
  streamingOffers: Offer[];
  negotiationStatus: "idle" | "streaming" | "complete" | "error";

  // Actions
  startAutoNegotiate: (sessionId: string) => void;
  stopStreaming: () => void;
  appendOffer: (offer: Offer) => void;
}
```

**Used by:** `/negotiate/[id]` page. Manages the SSE connection lifecycle for auto-negotiate.

#### `escrow.store.ts`

```typescript
interface EscrowState {
  pendingAction: {
    type: "fund" | "release" | "refund";
    escrowId: string;
  } | null;
  txInProgress: boolean;

  // Actions
  startAction: (type: string, escrowId: string) => void;
  confirmAction: () => Promise<void>;
  cancelAction: () => void;
}
```

**Purpose:** Manages the confirmation modal flow for escrow actions (fund/release/refund are irreversible blockchain transactions).

#### `notification.store.ts`

```typescript
interface NotificationState {
  toasts: Toast[];
  push: (toast: Omit<Toast, "id">) => void;
  dismiss: (id: string) => void;
}
```

### 5.2 Server State (SWR)

All data fetching uses SWR with consistent patterns:

```typescript
// Example: hooks/useSession.ts
export function useSession(sessionId: string) {
  const { data, error, isLoading, mutate } = useSWR(
    sessionId ? `/v1/sessions/${sessionId}` : null,
    (url) => sessionService.getSession(sessionId),
    {
      refreshInterval: 5000,       // Poll every 5s for active sessions
      revalidateOnFocus: true,
      dedupingInterval: 2000,
    }
  );

  return {
    session: data,
    isLoading,
    error,
    refetch: mutate,
  };
}
```

**SWR configuration by data type:**

| Data Type | Refresh Interval | Revalidate on Focus | Cache Time |
|---|---|---|---|
| Session list | 10s | Yes | 30s |
| Active session detail | 5s | Yes | 10s |
| Escrow status | 15s | Yes | 30s |
| Audit trail | None (manual) | Yes | 60s |
| Treasury dashboard | 30s | Yes | 60s |
| Marketplace search | None (on-demand) | No | 0s |
| FX rates | 60s | No | 300s |
| Health check | 30s | No | 10s |

### 5.3 Data Flow Diagram

```
User Action (click, form submit)
       │
       ▼
  Component (onClick / onSubmit handler)
       │
       ├──→ Zustand Store (if global state change)
       │        │
       │        ▼
       │    Re-render subscribed components
       │
       └──→ Service Layer (API call)
                │
                ▼
           Backend API (/v1/*)
                │
                ▼
           SWR Cache (auto-updates)
                │
                ▼
           Re-render with new data
```

**Blockchain Transaction Flow (Escrow):**
```
User clicks "Fund Escrow"
       │
       ▼
  EscrowStore.startAction("fund", escrowId)
       │
       ▼
  FundEscrowModal opens (confirmation)
       │
  User confirms
       │
       ▼
  EscrowStore.confirmAction()
       │
       ▼
  escrowService.fundEscrow(escrowId, mnemonic)
       │
       ▼
  POST /v1/escrow/{id}/fund
       │
       ▼
  Backend → Algorand SDK → Atomic group tx → Confirmation
       │
       ▼
  Response: { status: "funded", tx_id: "ALGO-TX-..." }
       │
       ▼
  SWR mutate → re-fetch escrow detail
       │
       ▼
  EscrowLifecycle component updates: DEPLOYED → FUNDED
       │
       ▼
  Toast: "Escrow funded. Tx: ALGO-TX-..."
```

---

## 6. Phase 1 — Blockchain Visibility Layer

### 6.1 Objective

Build the frontend components that display Algorand blockchain data. This phase doesn't change any UI flows — it adds the ability to show on-chain transaction IDs, application IDs, and explorer links throughout the app, aligned with the backend's migration to Algorand SDK.

### 6.2 UI/UX Scope

- `AlgorandTxLink` component for tx_id and app_id links
- Health check display showing Algorand node status
- Blockchain status indicator in `TopBar`

### 6.3 Technical Tasks

#### Task 1.1 — `AlgorandTxLink` Component

```typescript
// components/escrow/AlgorandTxLink.tsx

import { ExternalLink, Copy } from "lucide-react";
import { CopyButton } from "../ui/CopyButton";

const EXPLORER_BASE = {
  testnet: "https://testnet.explorer.perawallet.app",
  mainnet: "https://explorer.perawallet.app",
};

interface AlgorandTxLinkProps {
  txId?: string | null;
  appId?: number | null;
  network?: "testnet" | "mainnet";
  truncate?: boolean;
  label?: string;
}

export function AlgorandTxLink({
  txId,
  appId,
  network = "testnet",
  truncate = true,
  label,
}: AlgorandTxLinkProps) {
  if (!txId && !appId) return <span className="text-cad-text-muted">—</span>;

  const base = EXPLORER_BASE[network];
  const url = txId ? `${base}/tx/${txId}` : `${base}/application/${appId}`;
  const display = txId
    ? truncate ? `${txId.slice(0, 8)}...${txId.slice(-6)}` : txId
    : `App #${appId}`;

  return (
    <span className="inline-flex items-center gap-1.5 font-mono text-sm">
      {label && <span className="text-cad-text-muted">{label}:</span>}
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="text-cad-secondary hover:underline inline-flex items-center gap-1"
      >
        {display}
        <ExternalLink className="h-3 w-3" />
      </a>
      <CopyButton value={txId || String(appId)} />
    </span>
  );
}
```

#### Task 1.2 — `useAlgorandExplorer` Hook

```typescript
// hooks/useAlgorandExplorer.ts

const NETWORK = process.env.NEXT_PUBLIC_ALGORAND_NETWORK || "testnet";

export function useAlgorandExplorer() {
  const base =
    NETWORK === "mainnet"
      ? "https://explorer.perawallet.app"
      : "https://testnet.explorer.perawallet.app";

  return {
    txUrl: (txId: string) => `${base}/tx/${txId}`,
    appUrl: (appId: number) => `${base}/application/${appId}`,
    addressUrl: (addr: string) => `${base}/address/${addr}`,
    network: NETWORK,
  };
}
```

#### Task 1.3 — Blockchain Health in TopBar

Add a small status dot in the TopBar that reflects Algorand connectivity:

```typescript
// Within TopBar.tsx
// Fetches GET /health every 30s via SWR
// Shows green dot if services.algorand.healthy === true
// Shows red dot + tooltip if unhealthy
```

#### Task 1.4 — Algorand Types

```typescript
// types/algorand.types.ts

export interface AlgorandHealth {
  healthy: boolean;
  network: "testnet" | "mainnet";
  last_round: number;
  catchup_time: number;
  error?: string;
}

export interface AlgorandTxResult {
  tx_id: string;
  confirmed_round?: number;
}

export interface EscrowDeployResult {
  app_id: number;
  app_address: string;
  tx_id: string;
}
```

### 6.4 Dependencies on Backend APIs

| API | Usage |
|---|---|
| `GET /health` | Algorand node status in TopBar |

### 6.5 Expected Outputs

- `AlgorandTxLink` component (used by escrow, settlement, audit pages)
- `useAlgorandExplorer` hook
- Blockchain health indicator in TopBar
- `types/algorand.types.ts`
- No page changes — components are created but not yet integrated (integration happens in Phase 2)

---

## 7. Phase 2 — Escrow Lifecycle UI

### 7.1 Objective

Build the escrow management pages and components that let enterprise admins view, fund, release, and refund escrow contracts. This maps directly to the backend's rewritten `EscrowManager` (Algorand SDK, no simulation fallbacks).

### 7.2 UI/UX Scope

- `/dashboard/escrow` — List all escrow contracts
- `/dashboard/escrow/[id]` — Detailed view with lifecycle actions
- Modals for fund, release, refund confirmations
- Escrow lifecycle visualization
- Algorand tx links for every on-chain event

### 7.3 Technical Tasks

#### Task 2.1 — Escrow Service Layer

```typescript
// services/escrow.service.ts

import { apiClient } from "./api-client";
import type {
  EscrowData,
  EscrowFundRequest,
  EscrowRefundRequest,
  EscrowActionResult,
} from "@/types/escrow.types";

export const escrowService = {
  async getEscrow(escrowId: string): Promise<EscrowData> {
    const { data } = await apiClient.get(`/v1/escrow/${escrowId}`);
    return data;
  },

  async listEscrows(params?: {
    status?: string;
    page?: number;
    limit?: number;
  }): Promise<{ escrows: EscrowData[]; total: number }> {
    const { data } = await apiClient.get("/v1/escrow", { params });
    return data;
  },

  async fundEscrow(
    escrowId: string,
    payload: EscrowFundRequest
  ): Promise<EscrowActionResult> {
    const { data } = await apiClient.post(
      `/v1/escrow/${escrowId}/fund`,
      payload
    );
    return data;
  },

  async releaseEscrow(escrowId: string): Promise<EscrowActionResult> {
    const { data } = await apiClient.post(`/v1/escrow/${escrowId}/release`);
    return data;
  },

  async refundEscrow(
    escrowId: string,
    payload: EscrowRefundRequest
  ): Promise<EscrowActionResult> {
    const { data } = await apiClient.post(
      `/v1/escrow/${escrowId}/refund`,
      payload
    );
    return data;
  },
};
```

#### Task 2.2 — Escrow Types

```typescript
// types/escrow.types.ts

export interface EscrowData {
  escrow_id: string;
  session_id: string;
  status: "DEPLOYED" | "FUNDED" | "RELEASED" | "REFUNDED";
  app_id: number;
  amount: number;
  deploy_tx_id: string | null;
  fund_tx_id: string | null;
  release_tx_id: string | null;
  refund_tx_id: string | null;
  created_at: string;
}

export interface EscrowFundRequest {
  funder_mnemonic: string;
}

export interface EscrowRefundRequest {
  reason: string;
}

export interface EscrowActionResult {
  escrow_id: string;
  status: string;
  tx_id: string;
  merkle_root?: string;
  amount_microalgo?: number;
}
```

#### Task 2.3 — `useEscrow` Hook

```typescript
// hooks/useEscrow.ts

import useSWR from "swr";
import { escrowService } from "@/services/escrow.service";
import { useEscrowStore } from "@/stores/escrow.store";

export function useEscrow(escrowId: string) {
  const { data, error, isLoading, mutate } = useSWR(
    escrowId ? `escrow-${escrowId}` : null,
    () => escrowService.getEscrow(escrowId),
    { refreshInterval: 15000 }
  );

  const store = useEscrowStore();

  const fund = async (mnemonic: string) => {
    const result = await escrowService.fundEscrow(escrowId, {
      funder_mnemonic: mnemonic,
    });
    await mutate(); // Re-fetch to update UI
    return result;
  };

  const release = async () => {
    const result = await escrowService.releaseEscrow(escrowId);
    await mutate();
    return result;
  };

  const refund = async (reason: string) => {
    const result = await escrowService.refundEscrow(escrowId, { reason });
    await mutate();
    return result;
  };

  return {
    escrow: data,
    isLoading,
    error,
    fund,
    release,
    refund,
    refetch: mutate,
  };
}
```

#### Task 2.4 — `EscrowLifecycle` Component

A horizontal stepper showing the escrow state progression:

```typescript
// components/escrow/EscrowLifecycle.tsx

interface Step {
  key: string;
  label: string;
  txField: keyof EscrowData;
}

const STEPS: Step[] = [
  { key: "DEPLOYED", label: "Deployed", txField: "deploy_tx_id" },
  { key: "FUNDED",   label: "Funded",   txField: "fund_tx_id" },
  { key: "RELEASED", label: "Released", txField: "release_tx_id" },
];

// Renders 3 connected circles
// Current step: pulsing ring
// Completed steps: solid green with checkmark
// Each completed step shows AlgorandTxLink below
// REFUNDED shown as a branch from FUNDED if applicable
```

#### Task 2.5 — Escrow Action Modals

Three confirmation modals, each requiring explicit user input before executing irreversible blockchain operations:

**`FundEscrowModal`:**
- Shows: escrow amount, app_id, buyer address
- Input: Algorand wallet mnemonic (25-word)
- Warning: "This will transfer {amount} µALGO to the escrow contract. This action is irreversible."
- Submit → calls `escrow.fund()`
- On success: toast with tx_id + AlgorandTxLink

**`ReleaseEscrowModal`:**
- Shows: escrow amount, Merkle root, seller address
- Confirmation checkbox: "I confirm the goods/services have been delivered"
- Submit → calls `escrow.release()`
- On success: toast with tx_id

**`RefundEscrowModal`:**
- Shows: escrow amount, buyer address
- Input: reason (required, min 10 chars)
- Submit → calls `escrow.refund(reason)`
- On success: toast with tx_id

#### Task 2.6 — `/dashboard/escrow` Page

```typescript
// app/dashboard/escrow/page.tsx

// 1. Header: "Escrow Contracts" + filter bar (status dropdown)
// 2. DataTable with columns:
//    - Escrow ID (truncated, copyable)
//    - Session (link to session detail)
//    - Amount (formatted USDC)
//    - Status (StatusBadge)
//    - App ID (AlgorandTxLink)
//    - Created (relative time)
//    - Actions (view detail button)
// 3. Click row → navigate to /dashboard/escrow/[id]
// 4. Empty state if no escrows

// API: GET /v1/escrow?page=1&limit=20 (via escrowService.listEscrows)
```

#### Task 2.7 — `/dashboard/escrow/[id]` Page

```typescript
// app/dashboard/escrow/[id]/page.tsx

// Layout:
// ┌──────────────────────────────────────────┐
// │  Escrow #abc-123        Status: FUNDED   │
// │  Session: xyz-789 (link)                 │
// │  Amount: 50,200.00 USDC                  │
// ├──────────────────────────────────────────┤
// │  EscrowLifecycle (horizontal stepper)     │
// ├──────────────────────────────────────────┤
// │  Transaction Details                      │
// │  ┌─ Deploy Tx:  ALGO-TX-xxx (link) ────┐ │
// │  ├─ Fund Tx:    ALGO-TX-yyy (link) ────┤ │
// │  ├─ Release Tx: (pending)              ─┤ │
// │  └─ App ID:     12345678 (link) ───────┘ │
// ├──────────────────────────────────────────┤
// │  Actions (role-gated)                     │
// │  [Fund Escrow] [Release] [Refund]        │
// └──────────────────────────────────────────┘

// Actions visible based on escrow.status:
// DEPLOYED → [Fund Escrow]
// FUNDED   → [Release] [Refund]
// RELEASED / REFUNDED → no actions (read-only)

// API: GET /v1/escrow/{id}
```

### 7.4 Dependencies on Backend APIs

| API | Component/Page |
|---|---|
| `GET /v1/escrow/{id}` | Escrow detail page, useEscrow hook |
| `POST /v1/escrow/{id}/fund` | FundEscrowModal |
| `POST /v1/escrow/{id}/release` | ReleaseEscrowModal |
| `POST /v1/escrow/{id}/refund` | RefundEscrowModal |

### 7.5 Expected Outputs

- `/dashboard/escrow` page with filterable table
- `/dashboard/escrow/[id]` page with lifecycle visualization and action buttons
- 3 confirmation modals (Fund, Release, Refund)
- `EscrowLifecycle` stepper component
- `escrow.service.ts`, `escrow.types.ts`, `useEscrow.ts`, `escrow.store.ts`

---

## 8. Phase 3 — Payment & Settlement UI

### 8.1 Objective

Build the x402 payment flow UI and settlement view. Users can initiate payment delivery, view payment requirements, and track settlement status.

### 8.2 UI/UX Scope

- `/settlement/[id]` — Full settlement view for a session
- x402 payment requirement display
- Payment submission flow
- Delivery status tracking

### 8.3 Technical Tasks

#### Task 3.1 — Settlement Service Layer

```typescript
// services/settlement.service.ts

export const settlementService = {
  async initiateDelivery(sessionId: string): Promise<X402PaymentRequired> {
    const { data } = await apiClient.post("/v1/deliver/initiate", {
      session_id: sessionId,
      resource_url: `/v1/deliver/resource/${sessionId}`,
    });
    return data;
  },

  async submitPayment(
    sessionId: string,
    signedTxnBase64: string
  ): Promise<DeliveryResult> {
    const { data } = await apiClient.post(
      "/v1/deliver/submit",
      { session_id: sessionId },
      { headers: { "X-PAYMENT": signedTxnBase64 } }
    );
    return data;
  },
};
```

#### Task 3.2 — Settlement Types

```typescript
// types/settlement.types.ts (add to existing or create)

export interface X402PaymentRequired {
  x402_version: string;
  network: string;
  payment: {
    receiver: string;
    amount: number;
    note: string;
  };
  resource: string;
}

export interface DeliveryResult {
  status: "confirmed" | "simulated";
  tx_id: string;
  delivery_id: string;
}
```

#### Task 3.3 — `X402PaymentFlow` Component

```typescript
// components/settlement/X402PaymentFlow.tsx

// Three-step wizard:
// Step 1: "Payment Required" — shows receiver, amount, note
// Step 2: "Sign Transaction" — user pastes signed txn (base64) or
//         enters mnemonic for server-side signing
// Step 3: "Confirmed" — shows tx_id with AlgorandTxLink

// Each step animated with Framer Motion slide transition
```

#### Task 3.4 — `/settlement/[id]` Page

```typescript
// app/settlement/[id]/page.tsx

// Layout:
// ┌─────────────────────────────────────────────┐
// │  Settlement — Session xyz-789               │
// │  Status: AGREED → ESCROW DEPLOYED → PAYMENT │
// ├─────────────────────────────────────────────┤
// │  Counterparty: Delhi Exports Ltd            │
// │  Agreed Value: 50,200.00 USDC               │
// │  FX Rate (locked): 1 INR = 0.01193 USD     │
// ├─────────────────────────────────────────────┤
// │  X402PaymentFlow (wizard)                   │
// ├─────────────────────────────────────────────┤
// │  Delivery History                           │
// │  [Table of past delivery attempts]          │
// └─────────────────────────────────────────────┘

// APIs:
// GET /v1/sessions/{id} — session details + agreed value
// GET /v1/fx/rate — display FX rate
// POST /v1/deliver/initiate — get payment requirements
// POST /v1/deliver/submit — submit signed payment
```

#### Task 3.5 — FX Rate Display Hook

```typescript
// hooks/useFXRate.ts

export function useFXRate(from = "INR", to = "USD") {
  const { data, isLoading } = useSWR(
    `fx-${from}-${to}`,
    () => fxService.getRate(from, to),
    { refreshInterval: 60000 }
  );
  return { rate: data, isLoading };
}
```

### 8.4 Dependencies on Backend APIs

| API | Component/Page |
|---|---|
| `POST /v1/deliver/initiate` | X402PaymentFlow Step 1 |
| `POST /v1/deliver/submit` | X402PaymentFlow Step 2 |
| `GET /v1/fx/rate` | Settlement page FX display |
| `POST /v1/fx/convert` | Value conversion display |
| `GET /v1/sessions/{id}` | Session context |

### 8.5 Expected Outputs

- `/settlement/[id]` page with x402 payment wizard
- `X402PaymentFlow`, `PaymentRequirement`, `DeliveryStatus` components
- `settlement.service.ts`, `settlement.types.ts`
- FX rate display integration

---

## 9. Phase 4 — Rebrand, Cleanup & Multi-Tenancy

### 9.1 Objective

Rebrand the entire frontend from "A2A Treasury Network" to **Cadencia**. Strip demo scaffolding. Implement real KYC gating and agent config self-service. This is the cosmetic + structural cleanup phase.

### 9.2 UI/UX Scope

- Full rebrand: logo, colors, copy, metadata
- Remove demo page and demo-specific UI flows
- KYC verification screen (post-registration gate)
- Agent config form in settings
- Updated registration flow

### 9.3 Technical Tasks

#### Task 4.1 — Brand Assets & Metadata

```typescript
// app/layout.tsx — update metadata
export const metadata: Metadata = {
  title: "Cadencia — B2B Agentic Commerce",
  description:
    "Autonomous AI-powered B2B trade negotiation and settlement on Algorand",
  icons: { icon: "/favicon.ico" },
  openGraph: {
    title: "Cadencia",
    description: "Where AI agents negotiate, and blockchain settles.",
    siteName: "Cadencia",
  },
};
```

**Files to update with rebrand:**

| File | Change |
|---|---|
| `app/layout.tsx` | Metadata title, description, OG tags |
| `components/layout/Sidebar.tsx` | Logo + "Cadencia" text |
| `components/layout/TopBar.tsx` | Logo |
| `components/layout/PublicNav.tsx` | Logo + nav links |
| `components/landing/HeroSection.tsx` | Headline, tagline, brand name |
| `components/landing/FeaturesGrid.tsx` | Feature descriptions |
| `components/landing/StatsSection.tsx` | Platform name references |
| `components/landing/CTABanner.tsx` | Brand name |
| `components/landing/LogoStrip.tsx` | Update or remove partner logos |
| `lib/constants.ts` | `PLATFORM_NAME = "Cadencia"` |

#### Task 4.2 — Remove Demo Page

```bash
# DELETE these files/directories:
rm -rf src/app/demo/
```

Remove the "Demo" link from any navigation component. If a "Live Demo" section exists on the landing page, change it to a CTA that links to `/register`.

#### Task 4.3 — KYC Verification Flow

After registration, enterprises have `kyc_status=PENDING`. The dashboard should gate all functionality until KYC is complete.

**New component: `KYCVerificationForm`**

```typescript
// components/auth/KYCVerificationForm.tsx

// Shown on /dashboard when kyc_status === "PENDING"
// Full-page overlay or dedicated step in settings

// Fields:
// - PAN number (validated: XXXXX1234X pattern)
// - GST number (validated: 22XXXXX1234X1Z5 pattern)
// - Submit button

// API: POST /v1/enterprises/{id}/verify-kyc
// On success: kyc_status changes to ACTIVE, overlay dismissed,
//             full dashboard access unlocked
```

**Dashboard layout modification:**

```typescript
// app/dashboard/layout.tsx

// If enterprise.kyc_status === "PENDING":
//   Render KYCVerificationForm as full-page overlay
//   Sidebar and main content dimmed/disabled behind it
// Else:
//   Render normal dashboard
```

#### Task 4.4 — Updated Registration Flow

```typescript
// app/register/page.tsx

// Multi-step form:
// Step 1: Enterprise Details
//   - Legal name, PAN, GST, Geography (country select)
//   - Trade role (buyer / seller / both)
//   - Commodities (multi-select tag input)
//   - Min/max order value (number inputs)
// Step 2: Admin User
//   - Full name, email, password, confirm password
// Step 3: Review & Submit
//   - Summary of all inputs
//   - Submit → POST /v1/auth/register

// On success: redirect to /auth/login with success toast
```

**Zod validation schema:**

```typescript
// lib/validators.ts

import { z } from "zod";

export const registerSchema = z.object({
  enterprise: z.object({
    legal_name: z.string().min(3).max(200),
    pan: z.string().regex(/^[A-Z]{5}[0-9]{4}[A-Z]$/, "Invalid PAN format"),
    gst: z.string().regex(
      /^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][0-9A-Z][Z][0-9A-Z]$/,
      "Invalid GST format"
    ),
    geography: z.string().min(2).max(100),
    trade_role: z.enum(["buyer", "seller", "both"]),
    commodities: z.array(z.string()).min(1, "Select at least one commodity"),
    min_order_value: z.number().positive(),
    max_order_value: z.number().positive(),
  }),
  user: z.object({
    full_name: z.string().min(2).max(100),
    email: z.string().email(),
    password: z.string().min(8).max(128),
  }),
});
```

#### Task 4.5 — Agent Config Form in Settings

```typescript
// components/settings/AgentConfigForm.tsx

// Form fields mapping to PUT /v1/enterprises/{id}/agent-config:
// - Agent role: select (buyer / seller)
// - Intrinsic value: number input
// - Risk factor: slider (0.01 - 0.20)
// - Negotiation margin: slider (0.05 - 0.25)
// - Concession curve: select (linear / exponential / logarithmic)
// - Budget ceiling: number input (buyer only)
// - Max exposure: number input

// Validation with Zod
// Submit → PUT /v1/enterprises/{id}/agent-config
// Success toast: "Agent configuration saved"
```

#### Task 4.6 — Enterprise Profile in Settings

```typescript
// components/settings/EnterpriseProfile.tsx

// Read-only display of:
// - Enterprise ID (copyable)
// - Legal name
// - PAN / GST
// - KYC status (StatusBadge)
// - Wallet address (AlgorandTxLink → address explorer)
// - Trade role, commodities, value range
// - Agent card JSON (expandable code block)

// API: GET /v1/enterprises/{id}
```

### 9.4 Dependencies on Backend APIs

| API | Component/Page |
|---|---|
| `POST /v1/auth/register` | RegisterForm (updated with trade profile fields) |
| `POST /v1/enterprises/{id}/verify-kyc` | KYCVerificationForm |
| `PUT /v1/enterprises/{id}/agent-config` | AgentConfigForm |
| `GET /v1/enterprises/{id}` | EnterpriseProfile |
| `GET /health` | Platform name in health response |

### 9.5 Expected Outputs

- Complete rebrand to "Cadencia" across all pages
- Demo page removed
- KYC gate on dashboard (PENDING → verification form → ACTIVE)
- Multi-step registration with trade profile fields
- Agent config form in settings
- Enterprise profile display

---

## 10. Phase 5 — Marketplace Discovery UI

### 10.1 Objective

Build the marketplace where enterprises discover counterparties, evaluate match scores, and initiate trades. This is the core differentiator that transforms the app from a two-party demo into a real marketplace.

### 10.2 UI/UX Scope

- `/marketplace` — Search and browse counterparties
- `/marketplace/initiate/[id]` — Review counterparty and configure trade
- Matchmaking score visualization
- Handshake compatibility display
- Seamless flow from discovery → handshake → negotiation

### 10.3 Technical Tasks

#### Task 5.1 — Marketplace Service Layer

```typescript
// services/marketplace.service.ts

import { apiClient } from "./api-client";
import type {
  MarketplaceSearchParams,
  MarketplaceSearchResult,
  InitiateTradeRequest,
  InitiateTradeResult,
} from "@/types/marketplace.types";

export const marketplaceService = {
  async search(
    params: MarketplaceSearchParams
  ): Promise<MarketplaceSearchResult> {
    const { data } = await apiClient.get("/v1/marketplace/search", { params });
    return data;
  },

  async initiateTrade(
    payload: InitiateTradeRequest
  ): Promise<InitiateTradeResult> {
    const { data } = await apiClient.post("/v1/marketplace/initiate", payload);
    return data;
  },
};
```

#### Task 5.2 — Marketplace Types

```typescript
// types/marketplace.types.ts

export interface MarketplaceSearchParams {
  role?: "buyer" | "seller";
  commodity?: string;
  min_value?: number;
  max_value?: number;
  geography?: string;
  page?: number;
  limit?: number;
}

export interface CounterpartyResult {
  enterprise_id: string;
  legal_name: string;
  trade_role: "buyer" | "seller" | "both";
  commodities: string[];
  value_range: { min: number; max: number };
  geography: string;
  match_score: number;
  agent_card_url: string;
}

export interface MarketplaceSearchResult {
  results: CounterpartyResult[];
  total: number;
  page: number;
  limit: number;
}

export interface InitiateTradeRequest {
  counterparty_id: string;
  commodity: string;
  proposed_value: number;
  currency: string;
  max_rounds?: number;
  timeout_minutes?: number;
}

export interface InitiateTradeResult {
  handshake_id: string;
  compatible: boolean;
  shared_protocols: string[];
  session_id?: string;
  status: string;
  buyer_enterprise_id: string;
  seller_enterprise_id: string;
  reason?: string;
}
```

#### Task 5.3 — `SearchFilters` Component

```typescript
// components/marketplace/SearchFilters.tsx

// Horizontal filter bar at top of marketplace page:
//
// [Role: Buyer ▾] [Commodity: ______] [Min Value: ___] [Max Value: ___]
// [Geography: ▾]  [Search]  [Clear]
//
// Role: select (buyer / seller / all)
// Commodity: text input with debounce (500ms)
// Min/Max Value: number inputs
// Geography: select (IN, US, etc.)
// Search button triggers API call
// Clear resets all filters

// Uses useDebounce hook for commodity text input
// Filters stored in URL search params for shareable links
```

#### Task 5.4 — `CounterpartyCard` Component

```typescript
// components/marketplace/CounterpartyCard.tsx

interface CounterpartyCardProps {
  counterparty: CounterpartyResult;
  onInitiate: (id: string) => void;
}

// Card layout:
// ┌──────────────────────────────────┐
// │  Delhi Exports Ltd        [87%]  │  ← match score badge
// │  🏷 seller · 📍 IN               │
// │                                  │
// │  Commodities: steel, iron_ore    │
// │  Value Range: $5K – $200K        │
// │                                  │
// │  [View Agent Card]  [Initiate ▶] │
// └──────────────────────────────────┘
```

#### Task 5.5 — `MatchScoreBadge` Component

```typescript
// components/marketplace/MatchScoreBadge.tsx

// Circular badge showing match percentage:
// >= 80%: green ring
// 50-79%: amber ring
// < 50%: red ring
// Number displayed in center: "87%"
```

#### Task 5.6 — `/marketplace` Page

```typescript
// app/marketplace/page.tsx

// Layout:
// ┌──────────────────────────────────────────────┐
// │  Marketplace                                  │
// │  Find and connect with trade partners         │
// ├──────────────────────────────────────────────┤
// │  SearchFilters                                │
// ├──────────────────────────────────────────────┤
// │  Results: 42 counterparties found             │
// │                                               │
// │  ┌─────────────┐  ┌─────────────┐            │
// │  │ CounterpartyCard │ CounterpartyCard │       │
// │  └─────────────┘  └─────────────┘            │
// │  ┌─────────────┐  ┌─────────────┐            │
// │  │ CounterpartyCard │ CounterpartyCard │       │
// │  └─────────────┘  └─────────────┘            │
// │                                               │
// │  [1] [2] [3] ... [5] (pagination)            │
// └──────────────────────────────────────────────┘

// Grid: 2 columns on desktop, 1 on mobile
// Click "Initiate" → navigate to /marketplace/initiate/[enterprise_id]

// API: GET /v1/marketplace/search
```

#### Task 5.7 — `/marketplace/initiate/[id]` Page

```typescript
// app/marketplace/initiate/[id]/page.tsx

// Pre-negotiation setup page:
// ┌──────────────────────────────────────────────┐
// │  Initiate Trade with Delhi Exports Ltd       │
// ├──────────────────────────────────────────────┤
// │  Counterparty Profile                        │
// │  ┌─ Legal Name: Delhi Exports Ltd           │
// │  ├─ Trade Role: Seller                       │
// │  ├─ Commodities: steel, iron_ore             │
// │  ├─ Value Range: $5,000 – $200,000          │
// │  ├─ Geography: IN                            │
// │  └─ Agent Card: [View Full Card]             │
// ├──────────────────────────────────────────────┤
// │  Trade Configuration                         │
// │  ┌─ Commodity: [steel_coils ▾]              │
// │  ├─ Proposed Value: [45,000.00]             │
// │  ├─ Currency: USDC                           │
// │  ├─ Max Rounds: [10]                         │
// │  └─ Timeout: [30 min]                        │
// ├──────────────────────────────────────────────┤
// │  [Cancel]            [Initiate Negotiation ▶]│
// └──────────────────────────────────────────────┘

// On submit:
// 1. POST /v1/marketplace/initiate
// 2. If compatible=true → redirect to /negotiate/{session_id}
// 3. If compatible=false → show HandshakeResult with reason

// API:
// GET /v1/enterprises/{id} — counterparty profile
// POST /v1/marketplace/initiate — initiate trade
```

#### Task 5.8 — `HandshakeResult` Component

```typescript
// components/marketplace/HandshakeResult.tsx

interface HandshakeResultProps {
  result: InitiateTradeResult;
  onProceed?: () => void;   // Navigate to negotiation
  onBack?: () => void;      // Back to marketplace
}

// If compatible:
//   ✅ Handshake Successful
//   Shared Protocols: DANP-v1
//   Session created: [session_id]
//   [Proceed to Negotiation ▶]

// If incompatible:
//   ❌ Incompatible
//   Reason: "No shared settlement networks"
//   [Back to Marketplace]
```

### 10.4 Dependencies on Backend APIs

| API | Component/Page |
|---|---|
| `GET /v1/marketplace/search` | Marketplace page, SearchFilters |
| `POST /v1/marketplace/initiate` | Initiate trade page |
| `GET /v1/enterprises/{id}` | Counterparty profile display |
| `POST /v1/handshake` | Used internally by initiate endpoint |

### 10.5 Expected Outputs

- `/marketplace` page with search, filter, grid, pagination
- `/marketplace/initiate/[id]` page with trade configuration
- `CounterpartyCard`, `SearchFilters`, `MatchScoreBadge`, `HandshakeResult` components
- `marketplace.service.ts`, `marketplace.types.ts`, `useMarketplace.ts`
- Full flow: search → review → initiate → handshake → negotiation

---

## 11. Phase 6 — API Hardening & Auth Overhaul

### 11.1 Objective

Align the frontend with the backend's auth hardening: JWT refresh, API key management UI, improved error handling, rate limit awareness.

### 11.2 UI/UX Scope

- Token refresh flow (silent, transparent)
- API key management in settings
- Global error handling improvements
- Rate limit feedback to users

### 11.3 Technical Tasks

#### Task 6.1 — API Client Interceptors (Axios)

```typescript
// services/api-client.ts

import axios from "axios";
import { useAuthStore } from "@/stores/auth.store";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export const apiClient = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
  headers: { "Content-Type": "application/json" },
});

// Request interceptor: attach JWT
apiClient.interceptors.request.use((config) => {
  const token = useAuthStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor: handle 401, 429, standard errors
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;

    // 401 Unauthorized — attempt token refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;
      try {
        await useAuthStore.getState().refresh();
        const newToken = useAuthStore.getState().token;
        originalRequest.headers.Authorization = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch {
        useAuthStore.getState().logout();
        window.location.href = "/auth/login";
        return Promise.reject(error);
      }
    }

    // 429 Rate Limited
    if (error.response?.status === 429) {
      const { push } = useNotificationStore.getState();
      push({
        type: "warning",
        message: "Too many requests. Please wait a moment.",
      });
    }

    // Standard error format from backend
    const apiError = error.response?.data?.error;
    if (apiError) {
      return Promise.reject({
        code: apiError.code,
        message: apiError.message,
        details: apiError.details,
        status: error.response.status,
      });
    }

    return Promise.reject(error);
  }
);
```

#### Task 6.2 — Silent Token Refresh

```typescript
// stores/auth.store.ts — add refresh method

refresh: async () => {
  const { token } = get();
  if (!token) throw new Error("No token to refresh");

  const { data } = await axios.post(
    `${API_BASE}/v1/auth/refresh`,
    {},
    { headers: { Authorization: `Bearer ${token}` } }
  );

  set({ token: data.access_token });
  // Update cookie
  document.cookie = `a2a_token=${data.access_token}; path=/; max-age=${data.expires_in}; SameSite=Lax`;
},
```

#### Task 6.3 — API Key Manager Component

```typescript
// components/settings/APIKeyManager.tsx

// Layout:
// ┌──────────────────────────────────────────────┐
// │  API Keys                   [Create New Key] │
// ├──────────────────────────────────────────────┤
// │  Name            Prefix        Scopes        │
// │  production-key  cad_live_a1b2  read,write   │
// │  staging-key     cad_test_x3y4  read         │
// └──────────────────────────────────────────────┘

// Create New Key Modal:
// - Name input
// - Scopes: multi-select checkboxes
//   [x] read:sessions  [x] write:sessions
//   [ ] read:escrow    [ ] write:escrow
//   [ ] read:audit
// - Submit → POST /v1/auth/api-keys
// - On success: show key ONCE in a highlighted box with copy button
//   "⚠ Copy this key now. It won't be shown again."

// API: POST /v1/auth/api-keys
```

#### Task 6.4 — Global Error Banner Component

```typescript
// components/ui/ErrorBanner.tsx

interface ErrorBannerProps {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
  };
  onDismiss?: () => void;
  onRetry?: () => void;
}

// Red banner with:
// - Error code (monospace)
// - Human-readable message
// - Optional "Retry" button
// - Dismiss X button
// - Expandable "Details" section for debug info
```

#### Task 6.5 — Rate Limit Feedback

When the user hits a 429, show a cooldown indicator instead of allowing repeated clicks:

```typescript
// hooks/useRateLimitAware.ts

export function useRateLimitAware() {
  const [cooldown, setCooldown] = useState(false);
  const [retryAfter, setRetryAfter] = useState(0);

  const handleError = (error: any) => {
    if (error?.status === 429) {
      const retry = parseInt(error.headers?.["retry-after"] || "60");
      setCooldown(true);
      setRetryAfter(retry);
      setTimeout(() => setCooldown(false), retry * 1000);
    }
  };

  return { cooldown, retryAfter, handleError };
}
```

### 11.4 Dependencies on Backend APIs

| API | Component/Page |
|---|---|
| `POST /v1/auth/refresh` | API client interceptor |
| `POST /v1/auth/api-keys` | APIKeyManager |
| All endpoints (error format) | ErrorBanner, global interceptor |

### 11.5 Expected Outputs

- Axios interceptors: auto-refresh on 401, rate limit toast on 429
- Silent token refresh (no user interaction needed)
- API Key management UI in settings
- Global error banner component
- Rate limit awareness in hooks

---

## 12. Phase 7 — Deployment & Production Readiness

### 12.1 Objective

Configure the frontend for production deployment alongside the backend. Optimize builds, set production environment variables, and ensure the app works with the production API and HTTPS.

### 12.2 UI/UX Scope

- No new pages or components
- Production build optimization
- Environment configuration
- SEO and meta tags
- Performance monitoring setup

### 12.3 Technical Tasks

#### Task 7.1 — Production Environment

```bash
# .env.production

NEXT_PUBLIC_API_URL=https://api.cadencia.app
NEXT_PUBLIC_PLATFORM_NAME=Cadencia
NEXT_PUBLIC_ALGORAND_NETWORK=testnet
NEXT_PUBLIC_ALGORAND_EXPLORER=https://testnet.explorer.perawallet.app
```

#### Task 7.2 — Next.js Configuration

```typescript
// next.config.ts

import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",  // Optimized Docker output
  poweredByHeader: false,
  reactStrictMode: true,

  images: {
    remotePatterns: [
      { protocol: "https", hostname: "**.cadencia.app" },
    ],
  },

  async rewrites() {
    return [
      // Proxy API calls in production to avoid CORS
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL}/v1/:path*`,
      },
    ];
  },

  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          {
            key: "Referrer-Policy",
            value: "strict-origin-when-cross-origin",
          },
          {
            key: "Content-Security-Policy",
            value:
              "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: https:; connect-src 'self' https://api.cadencia.app",
          },
        ],
      },
    ];
  },
};

export default config;
```

#### Task 7.3 — Auth Middleware Update

```typescript
// middleware.ts

import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

const PUBLIC_ROUTES = ["/", "/auth/login", "/register", "/pricing"];
const AUTH_ROUTES = ["/auth/login", "/register"];

export function middleware(request: NextRequest) {
  const token = request.cookies.get("a2a_token")?.value;
  const { pathname } = request.nextUrl;

  // Protect dashboard, marketplace, negotiate, settlement, treasury
  const isProtected =
    pathname.startsWith("/dashboard") ||
    pathname.startsWith("/marketplace") ||
    pathname.startsWith("/negotiate") ||
    pathname.startsWith("/settlement") ||
    pathname.startsWith("/treasury");

  if (isProtected && !token) {
    const loginUrl = new URL("/auth/login", request.url);
    loginUrl.searchParams.set("redirect", pathname);
    return NextResponse.redirect(loginUrl);
  }

  // Redirect authenticated users away from auth pages
  if (AUTH_ROUTES.some((r) => pathname.startsWith(r)) && token) {
    return NextResponse.redirect(new URL("/dashboard", request.url));
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon.ico|.*\\.png$|.*\\.svg$).*)",
  ],
};
```

#### Task 7.4 — Docker Configuration for Frontend

```dockerfile
# Dockerfile (a2a-treasury-ui)
FROM node:20-alpine AS base

FROM base AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --only=production

FROM base AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM base AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

RUN addgroup --system --gid 1001 nodejs
RUN adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs
EXPOSE 3000
ENV PORT=3000

CMD ["node", "server.js"]
```

#### Task 7.5 — Add Frontend to `docker-compose.prod.yml`

```yaml
# Add to the backend's docker-compose.prod.yml
  frontend:
    build:
      context: ./a2a-treasury-ui
      dockerfile: Dockerfile
    environment:
      - NEXT_PUBLIC_API_URL=http://api:8000
    ports:
      - "3000:3000"
    depends_on:
      api:
        condition: service_healthy
```

Update the Caddy reverse proxy:

```
# Caddyfile — add frontend routing
cadencia.app {
    # Frontend
    reverse_proxy /api/* api:8000
    reverse_proxy frontend:3000

    encode gzip
    header {
        Strict-Transport-Security "max-age=31536000"
        X-Content-Type-Options "nosniff"
        X-Frame-Options "DENY"
    }
}
```

#### Task 7.6 — Loading States & Skeleton Screens

Ensure every page has proper loading states for production:

```typescript
// app/dashboard/page.tsx — example loading.tsx file

// app/dashboard/loading.tsx
export default function DashboardLoading() {
  return (
    <div className="space-y-6 p-6">
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
      <Skeleton className="h-64 rounded-lg" />
      <Skeleton className="h-48 rounded-lg" />
    </div>
  );
}
```

Create `loading.tsx` for: `/dashboard`, `/dashboard/sessions`, `/dashboard/escrow`, `/marketplace`, `/treasury`.

### 12.4 Dependencies on Backend APIs

| API | Usage |
|---|---|
| `GET /health` | Frontend health-check probe |
| All APIs | Verified working in production environment |

### 12.5 Expected Outputs

- `.env.production` for frontend
- Optimized `next.config.ts` with security headers, rewrites
- Updated `middleware.ts` for production auth
- `Dockerfile` for standalone Next.js build
- Frontend added to `docker-compose.prod.yml`
- Caddy routing for frontend + API
- Loading skeletons for all major pages

---

## 13. Complete API Integration Map

This maps every backend API endpoint to the frontend pages and components that consume it.

### 13.1 Authentication APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `POST /v1/auth/register` | POST | `/register` | `RegisterForm` |
| `POST /v1/auth/login` | POST | `/auth/login` | `LoginForm` |
| `POST /v1/auth/refresh` | POST | Global (interceptor) | `api-client.ts` |
| `POST /v1/auth/api-keys` | POST | `/dashboard/settings` | `APIKeyManager` |

### 13.2 Enterprise APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/enterprises/{id}` | GET | Settings, Marketplace initiate | `EnterpriseProfile`, `InitiateTradeForm` |
| `PUT /v1/enterprises/{id}/agent-config` | PUT | `/dashboard/settings` | `AgentConfigForm` |
| `POST /v1/enterprises/{id}/verify-kyc` | POST | Dashboard (KYC gate) | `KYCVerificationForm` |

### 13.3 Marketplace APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/marketplace/search` | GET | `/marketplace` | `MarketplaceGrid`, `SearchFilters` |
| `POST /v1/marketplace/initiate` | POST | `/marketplace/initiate/[id]` | `InitiateTradeForm` |

### 13.4 Session APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `POST /v1/sessions` | POST | Marketplace initiate (internal) | `InitiateTradeForm` |
| `POST /v1/sessions/{id}/action` | POST | `/negotiate/[id]` | `NegotiationControls` |
| `POST /v1/sessions/{id}/auto-negotiate` | POST (SSE) | `/negotiate/[id]` | `SSEStreamHandler` |
| `GET /v1/sessions` | GET | `/dashboard/sessions` | `SessionsTable` |
| `GET /v1/sessions/{id}` | GET | `/dashboard/sessions/[id]`, `/negotiate/[id]` | `SessionDetail` |

### 13.5 Escrow APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/escrow/{id}` | GET | `/dashboard/escrow/[id]` | `EscrowDetail`, `EscrowLifecycle` |
| `POST /v1/escrow/{id}/fund` | POST | `/dashboard/escrow/[id]` | `FundEscrowModal` |
| `POST /v1/escrow/{id}/release` | POST | `/dashboard/escrow/[id]` | `ReleaseEscrowModal` |
| `POST /v1/escrow/{id}/refund` | POST | `/dashboard/escrow/[id]` | `RefundEscrowModal` |

### 13.6 Settlement APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `POST /v1/deliver/initiate` | POST | `/settlement/[id]` | `X402PaymentFlow` |
| `POST /v1/deliver/submit` | POST | `/settlement/[id]` | `X402PaymentFlow` |

### 13.7 Audit APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/audit/{type}/{id}` | GET | `/dashboard/audit` | `AuditTrailViewer` |
| `GET /v1/audit/{session_id}/merkle` | GET | `/dashboard/audit`, Session detail | `MerkleProofPanel` |
| `POST /v1/audit/verify` | POST | `/dashboard/audit` | `MerkleProofPanel` |

### 13.8 FX APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/fx/rate` | GET | `/settlement/[id]`, Dashboard | `useFXRate` hook |
| `POST /v1/fx/convert` | POST | Settlement page | `X402PaymentFlow` |

### 13.9 Compliance APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `POST /v1/compliance/check` | POST | (triggered by backend) | — |
| `GET /v1/compliance/records` | GET | `/dashboard/compliance` | `ComplianceTable` |

### 13.10 Treasury APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/treasury/dashboard` | GET | `/treasury` | `PortfolioMetrics`, charts |

### 13.11 Framework APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /v1/framework/protocols` | GET | Marketplace initiate | Protocol selector |
| `GET /v1/framework/settlement-providers` | GET | Marketplace initiate | Settlement info |

### 13.12 Handshake API

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `POST /v1/handshake` | POST | (called internally by marketplace/initiate) | `HandshakeResult` |

### 13.13 System APIs

| Endpoint | Method | Frontend Consumer | Component |
|---|---|---|---|
| `GET /health` | GET | TopBar, monitoring | Health indicator |
| `GET /.well-known/agent.json` | GET | Landing page (optional) | `AgentCard` |

---

## 14. Error Handling Strategy

### 14.1 Error Categories

| HTTP Status | Category | User-Facing Behavior |
|---|---|---|
| 400 | Validation Error | Highlight specific form field, show message below input |
| 401 | Unauthorized | Silent refresh attempt → if fails, redirect to login |
| 403 | Forbidden | Toast: "You don't have permission for this action" |
| 404 | Not Found | Show EmptyState: "Resource not found" |
| 409 | Conflict | Context-specific: "Draft already exists", "Escrow already deployed" |
| 422 | Unprocessable Entity | Show field-level validation errors from backend |
| 429 | Rate Limited | Toast: "Please wait" + cooldown indicator |
| 500 | Server Error | ErrorBanner: "Something went wrong. Please try again." |
| Network Error | Connection Failed | Toast: "Unable to reach server. Check your connection." |

### 14.2 Error Handling by Context

**Form submissions:** Display inline errors below the relevant field. Use Zod client-side validation to catch issues before hitting the API. On API 422, map `details` to form fields.

**Data fetching (SWR):** Show Skeleton during loading. On error, show `ErrorBanner` with retry button. SWR auto-retries on focus/reconnect.

**Blockchain operations (escrow fund/release/refund):** These are high-stakes. Show ConfirmDialog before execution. During execution, show loading spinner with "Broadcasting to Algorand..." On success, show toast with tx_id link. On failure, show detailed ErrorBanner (the blockchain error message is important for debugging).

**SSE streams (auto-negotiate):** On SSE connection error, show reconnecting indicator. After 3 failed reconnect attempts, show "Negotiation stream lost" with manual retry button.

### 14.3 Error Type Definitions

```typescript
// types/api.ts — add to existing

export interface APIError {
  code: string;
  message: string;
  details?: Record<string, unknown>;
  status: number;
}

export function isAPIError(error: unknown): error is APIError {
  return (
    typeof error === "object" &&
    error !== null &&
    "code" in error &&
    "message" in error
  );
}
```

---

## 15. Testing Strategy

### 15.1 Unit Tests (Jest + React Testing Library)

Test all service layer functions with mocked Axios:

```typescript
// __tests__/services/escrow.service.test.ts
// Mock apiClient, test each method's request format and response parsing
```

Test all custom hooks with renderHook:

```typescript
// __tests__/hooks/useEscrow.test.ts
// Mock SWR, test data flow, action triggers, error states
```

Test UI primitives:

```typescript
// __tests__/components/StatusBadge.test.ts
// Verify correct color/label for every status string
```

### 15.2 Integration Tests (Playwright)

Critical user flows to test end-to-end:

| Flow | Steps |
|---|---|
| Registration | Fill form → submit → redirect to login |
| Login | Enter credentials → redirect to dashboard |
| KYC Gate | Login with PENDING enterprise → see KYC form → verify → dashboard unlocked |
| Marketplace Search | Navigate → apply filters → see results |
| Initiate Trade | Select counterparty → configure → submit → handshake result |
| Auto-Negotiate | Start negotiation → SSE stream renders → AGREED state |
| Escrow Fund | Navigate to escrow → click fund → modal → confirm → success toast |
| Audit Verify | View audit trail → click verify Merkle → see result |

### 15.3 Test File Locations

```
__tests__/
├── services/
│   ├── auth.service.test.ts
│   ├── escrow.service.test.ts
│   ├── marketplace.service.test.ts
│   └── session.service.test.ts
├── hooks/
│   ├── useAuth.test.ts
│   ├── useEscrow.test.ts
│   └── useSSE.test.ts
├── components/
│   ├── StatusBadge.test.ts
│   ├── AlgorandTxLink.test.ts
│   └── EscrowLifecycle.test.ts
└── pages/
    └── dashboard.test.ts

e2e/
├── auth.spec.ts
├── marketplace.spec.ts
├── negotiation.spec.ts
├── escrow.spec.ts
└── audit.spec.ts
```

---

> **Summary:** This plan covers 17 pages, ~60 components, 12 service modules, 4 Zustand stores, 9 custom hooks, and maps every backend API to its frontend consumer. The 7 phases mirror the backend plan exactly: blockchain visibility → escrow UI → settlement UI → rebrand/cleanup → marketplace → auth hardening → deployment. Estimated effort: ~8–10 days for a focused frontend sprint, parallelizable with backend work starting from Phase 4.
