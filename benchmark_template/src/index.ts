export type EventType =
  | "account_opened"
  | "plan_changed"
  | "payment_succeeded"
  | "payment_failed"
  | "coupon_applied"
  | "usage_recorded"
  | "account_closed";

export type PlanName = "free" | "starter" | "pro" | "enterprise";

export interface PlanDefinition {
  priceCents: number;
  features: string[];
  usageLimit: number;
}

export const PLAN_DEFINITIONS: Record<PlanName, PlanDefinition> = {
  free: {
    priceCents: 0,
    features: ["dashboard"],
    usageLimit: 100
  },
  starter: {
    priceCents: 1200,
    features: ["dashboard", "exports"],
    usageLimit: 1000
  },
  pro: {
    priceCents: 4900,
    features: ["dashboard", "exports", "priority_support", "rules"],
    usageLimit: 10000
  },
  enterprise: {
    priceCents: 19900,
    features: ["audit_log", "dashboard", "exports", "priority_support", "rules", "sso"],
    usageLimit: 100000
  }
};

export const COUPON_DEFINITIONS: Record<string, { discountPercent: number }> = {
  SAVE10: { discountPercent: 10 },
  WELCOME50: { discountPercent: 50 }
};

export interface RawEvent {
  [key: string]: unknown;
}

export interface NormalizedEvent {
  id: string;
  accountId: string;
  type: EventType;
  timestamp: string;
  plan?: PlanName;
  amountCents?: number;
  couponCode?: string;
  couponExpiresAt?: string | null;
  usage?: number;
}

export interface AccountState {
  accountId: string;
  status: "active" | "past_due" | "closed";
  plan: PlanName;
  totalPaidCents: number;
  failedPayments: number;
  usage: number;
  couponCode: string | null;
  couponExpiresAt: string | null;
  closedAt: string | null;
  lastEventAt: string | null;
}

export interface EntitlementState {
  active: boolean;
  features: string[];
  usageLimit: number;
  overLimit: boolean;
  couponActive: boolean;
}

export interface AccountSummary {
  accountId: string;
  status: "active" | "past_due" | "closed";
  plan: PlanName;
  features: string[];
  usage: number;
  usageLimit: number;
  overLimit: boolean;
  totalPaidCents: number;
  couponCode: string | null;
  couponActive: boolean;
  closedAt: string | null;
  lastEventAt: string | null;
}

export type ParseResult =
  | { ok: true; value: RawEvent }
  | { ok: false; error: string; line: string };

export type NormalizeResult =
  | { ok: true; value: NormalizedEvent }
  | { ok: false; error: string; issues: string[]; raw: RawEvent };

const EVENT_TYPES = new Set<EventType>([
  "account_opened",
  "plan_changed",
  "payment_succeeded",
  "payment_failed",
  "coupon_applied",
  "usage_recorded",
  "account_closed"
]);

const PLAN_NAMES = new Set<PlanName>(["free", "starter", "pro", "enterprise"]);

export function parseEventLine(line: string): ParseResult {
  if (line.trim() === "") {
    return { ok: false, error: "empty_line", line };
  }

  try {
    const parsed = JSON.parse(line) as unknown;
    if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) {
      return { ok: false, error: "non_object_json", line };
    }
    return { ok: true, value: parsed as RawEvent };
  } catch {
    return { ok: false, error: "invalid_json", line };
  }
}

export function normalizeEvent(raw: RawEvent): NormalizeResult {
  const issues: string[] = [];
  const id = readRequiredString(raw, "id", issues);
  const accountId = readRequiredString(raw, "account_id", issues);
  const rawType = readRequiredString(raw, "type", issues);
  const rawTimestamp = readRequiredString(raw, "timestamp", issues);

  let type: EventType = "account_opened";
  if (rawType !== undefined) {
    if (EVENT_TYPES.has(rawType as EventType)) {
      type = rawType as EventType;
    } else {
      issues.push("invalid_type");
    }
  }

  const timestamp = normalizeTimestamp(rawTimestamp, issues, "timestamp");
  const normalized: NormalizedEvent = {
    id: id ?? "",
    accountId: accountId ?? "",
    type,
    timestamp: timestamp ?? ""
  };

  if (typeof raw.plan === "string") {
    const plan = raw.plan.trim();
    if (PLAN_NAMES.has(plan as PlanName)) {
      normalized.plan = plan as PlanName;
    } else {
      issues.push("invalid_plan");
    }
  }

  if (raw.amount !== undefined) {
    const amountCents = parseMoneyToCents(raw.amount);
    if (amountCents === null) {
      issues.push("invalid_amount");
    } else {
      normalized.amountCents = amountCents;
    }
  }

  if (typeof raw.coupon === "string" && raw.coupon.trim() !== "") {
    normalized.couponCode = raw.coupon.trim().toUpperCase();
  }

  if (typeof raw.expires_at === "string" && raw.expires_at.trim() !== "") {
    const expiresAt = normalizeTimestamp(raw.expires_at, issues, "invalid_coupon_expiration");
    normalized.couponExpiresAt = expiresAt;
  }

  if (raw.usage !== undefined) {
    if (typeof raw.usage === "number" && Number.isInteger(raw.usage) && raw.usage >= 0) {
      normalized.usage = raw.usage;
    } else {
      issues.push("invalid_usage");
    }
  }

  if (issues.length > 0) {
    return { ok: false, error: "invalid_event", issues, raw };
  }

  return { ok: true, value: normalized };
}

export function reduceAccountState(events: NormalizedEvent[]): AccountState[] {
  const states = new Map<string, AccountState>();

  for (const event of events) {
    const state = getOrCreateState(states, event.accountId);

    if (event.type === "account_opened" || event.type === "plan_changed") {
      state.plan = event.plan ?? state.plan;
      state.status = state.status === "closed" ? "closed" : "active";
    }

    if (event.type === "payment_succeeded") {
      state.totalPaidCents += event.amountCents ?? 0;
      if (state.status !== "closed") {
        state.status = "active";
      }
    }

    if (event.type === "payment_failed") {
      state.failedPayments += 1;
      if (state.status !== "closed") {
        state.status = "past_due";
      }
    }

    if (event.type === "usage_recorded") {
      state.usage += event.usage ?? 0;
    }

    if (event.type === "account_closed") {
      state.status = "closed";
      state.closedAt = event.timestamp;
    }

    state.lastEventAt = event.timestamp;
  }

  return [...states.values()].sort((a, b) => a.accountId.localeCompare(b.accountId));
}

export function evaluateEntitlements(state: AccountState, asOf?: string): EntitlementState {
  const plan = PLAN_DEFINITIONS[state.plan];
  const couponActive =
    state.couponCode !== null &&
    state.couponExpiresAt !== null &&
    (asOf === undefined || state.couponExpiresAt >= asOf);

  if (state.status === "closed") {
    return {
      active: false,
      features: [],
      usageLimit: 0,
      overLimit: state.usage > 0,
      couponActive
    };
  }

  return {
    active: state.status === "active",
    features: [...plan.features],
    usageLimit: plan.usageLimit,
    overLimit: state.usage > plan.usageLimit,
    couponActive
  };
}

export function summarizeAccount(state: AccountState, asOf?: string): AccountSummary {
  const entitlements = evaluateEntitlements(state, asOf);
  return {
    accountId: state.accountId,
    status: state.status,
    plan: state.plan,
    features: entitlements.features,
    usage: state.usage,
    usageLimit: entitlements.usageLimit,
    overLimit: entitlements.overLimit,
    totalPaidCents: state.totalPaidCents,
    couponCode: state.couponCode,
    couponActive: entitlements.couponActive,
    closedAt: state.closedAt,
    lastEventAt: state.lastEventAt
  };
}

export function exportLedgerReport(summaries: AccountSummary[]): string {
  const header = [
    "account_id",
    "status",
    "plan",
    "total_paid_cents",
    "usage",
    "usage_limit",
    "over_limit",
    "coupon_code",
    "coupon_active",
    "closed_at",
    "last_event_at"
  ];

  const rows = [...summaries]
    .sort((a, b) => a.accountId.localeCompare(b.accountId))
    .map((summary) => [
      summary.accountId,
      summary.status,
      summary.plan,
      String(summary.totalPaidCents),
      String(summary.usage),
      String(summary.usageLimit),
      String(summary.overLimit),
      summary.couponCode ?? "",
      String(summary.couponActive),
      summary.closedAt ?? "",
      summary.lastEventAt ?? ""
    ]);

  return [header, ...rows].map((row) => row.join(",")).join("\n") + "\n";
}

function readRequiredString(raw: RawEvent, field: string, issues: string[]): string | undefined {
  const value = raw[field];
  if (typeof value !== "string") {
    issues.push(`missing_${field}`);
    return undefined;
  }

  const trimmed = value.trim();
  if (trimmed === "") {
    issues.push(`blank_${field}`);
    return undefined;
  }

  return trimmed;
}

function normalizeTimestamp(value: string | undefined, issues: string[], issueCode: string): string | null {
  if (value === undefined) {
    return null;
  }

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    issues.push(issueCode);
    return null;
  }

  return date.toISOString();
}

function parseMoneyToCents(value: unknown): number | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  if (!/^\d+\.\d{2}$/.test(trimmed)) {
    return null;
  }

  const [dollars, cents] = trimmed.split(".");
  return Number(dollars) * 100 + Number(cents);
}

function getOrCreateState(states: Map<string, AccountState>, accountId: string): AccountState {
  const existing = states.get(accountId);
  if (existing !== undefined) {
    return existing;
  }

  const state: AccountState = {
    accountId,
    status: "active",
    plan: "free",
    totalPaidCents: 0,
    failedPayments: 0,
    usage: 0,
    couponCode: null,
    couponExpiresAt: null,
    closedAt: null,
    lastEventAt: null
  };
  states.set(accountId, state);
  return state;
}
