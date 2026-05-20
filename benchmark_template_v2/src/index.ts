export type EventType =
  | "account_opened"
  | "plan_changed"
  | "payment_succeeded"
  | "payment_failed"
  | "coupon_applied"
  | "usage_recorded"
  | "account_closed"
  | "invoice_issued"
  | "account_merged"
  | "event_corrected"
  | "event_voided"
  | "seat_delta_recorded";

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
  effectiveAt: string;
  recordedAt: string;
  sequence: number;
  plan?: PlanName;
  amountCents?: number;
  currency?: string;
  couponCode?: string;
  couponExpiresAt?: string | null;
  usage?: number;
  quantity?: number;
  seatDelta?: number;
  mergeFromAccountId?: string;
  correctionOf?: string;
  voidedEventId?: string;
  invoiceId?: string;
  periodStart?: string;
  periodEnd?: string;
}

export interface AccountState {
  accountId: string;
  status: "active" | "past_due" | "closed";
  plan: PlanName;
  totalPaidCents: number;
  failedPayments: number;
  usage: number;
  currency: string | null;
  seats: number;
  couponCode: string | null;
  couponExpiresAt: string | null;
  invoiceIds: string[];
  lastInvoiceId: string | null;
  lastPeriodStart: string | null;
  lastPeriodEnd: string | null;
  mergedFromAccountIds: string[];
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
  currency: string | null;
  seats: number;
  couponCode: string | null;
  couponActive: boolean;
  invoiceIds: string[];
  lastInvoiceId: string | null;
  lastPeriodStart: string | null;
  lastPeriodEnd: string | null;
  mergedFromAccountIds: string[];
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
  "account_closed",
  "invoice_issued",
  "account_merged",
  "event_corrected",
  "event_voided",
  "seat_delta_recorded"
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

  const timestamp = normalizeTimestamp(rawTimestamp, issues, "invalid_timestamp");
  const effectiveAt =
    normalizeOptionalTimestamp(raw, "effective_at", issues, "invalid_effective_at") ?? timestamp;
  const recordedAt =
    normalizeOptionalTimestamp(raw, "recorded_at", issues, "invalid_recorded_at") ?? timestamp;
  const sequence = readOptionalInteger(raw, "sequence", issues, "invalid_sequence", {
    min: 0,
    defaultValue: 0
  }) ?? 0;

  const normalized: NormalizedEvent = {
    id: id ?? "",
    accountId: accountId ?? "",
    type,
    timestamp: timestamp ?? "",
    effectiveAt: effectiveAt ?? "",
    recordedAt: recordedAt ?? "",
    sequence
  };

  if (typeof raw.plan === "string") {
    const plan = raw.plan.trim();
    if (PLAN_NAMES.has(plan as PlanName)) {
      normalized.plan = plan as PlanName;
    } else {
      issues.push("invalid_plan");
    }
  }

  if (raw.amount_cents !== undefined) {
    const amountCents = readIntegerValue(raw.amount_cents, { min: 0 });
    if (amountCents === null) {
      issues.push("invalid_amount_cents");
    } else {
      normalized.amountCents = amountCents;
    }
  } else if (raw.amount !== undefined) {
    const amountCents = parseMoneyToCents(raw.amount);
    if (amountCents === null) {
      issues.push("invalid_amount");
    } else {
      normalized.amountCents = amountCents;
    }
  }

  const currency = normalizeCurrency(raw.currency);
  if (currency === null && raw.currency !== undefined) {
    issues.push("invalid_currency");
  } else if (currency !== undefined && currency !== null) {
    normalized.currency = currency;
  }

  if (typeof raw.coupon === "string" && raw.coupon.trim() !== "") {
    normalized.couponCode = raw.coupon.trim().toUpperCase();
  }

  if (typeof raw.expires_at === "string" && raw.expires_at.trim() !== "") {
    normalized.couponExpiresAt = normalizeTimestamp(raw.expires_at, issues, "invalid_coupon_expiration");
  }

  if (raw.usage !== undefined) {
    const usage = readIntegerValue(raw.usage, { min: 0 });
    if (usage === null) {
      issues.push("invalid_usage");
    } else {
      normalized.usage = usage;
    }
  }

  const quantity = readOptionalInteger(raw, "quantity", issues, "invalid_quantity", { min: 0 });
  if (quantity !== undefined) {
    normalized.quantity = quantity;
  }

  const seatDelta = readOptionalInteger(raw, "seat_delta", issues, "invalid_seat_delta");
  if (seatDelta !== undefined) {
    normalized.seatDelta = seatDelta;
  }

  copyOptionalId(raw, normalized, "merge_from_account_id", "mergeFromAccountId", issues);
  copyOptionalId(raw, normalized, "correction_of", "correctionOf", issues);
  copyOptionalId(raw, normalized, "voided_event_id", "voidedEventId", issues);
  copyOptionalId(raw, normalized, "invoice_id", "invoiceId", issues);
  copyOptionalTimestamp(raw, normalized, "period_start", "periodStart", issues, "invalid_period_start");
  copyOptionalTimestamp(raw, normalized, "period_end", "periodEnd", issues, "invalid_period_end");

  if (issues.length > 0) {
    return { ok: false, error: "invalid_event", issues, raw };
  }

  return { ok: true, value: normalized };
}

export function reduceAccountState(events: NormalizedEvent[]): AccountState[] {
  const states = new Map<string, AccountState>();
  const seenEventIds = new Set<string>();
  const orderedEvents = [...events].sort(compareReplayOrder);

  for (const event of orderedEvents) {
    if (seenEventIds.has(event.id)) {
      continue;
    }
    seenEventIds.add(event.id);

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

    if (event.type === "coupon_applied") {
      state.couponCode = event.couponCode ?? state.couponCode;
      state.couponExpiresAt = event.couponExpiresAt ?? state.couponExpiresAt;
    }

    if (event.type === "usage_recorded") {
      state.usage += event.usage ?? event.quantity ?? 0;
    }

    if (event.type === "account_closed") {
      state.status = "closed";
      state.closedAt = event.effectiveAt;
    }

    if (event.seatDelta !== undefined) {
      state.seats = Math.max(0, state.seats + event.seatDelta);
    } else if (event.type === "account_opened" && event.quantity !== undefined) {
      state.seats = Math.max(1, event.quantity);
    }

    if (event.currency !== undefined) {
      state.currency = event.currency;
    }

    if (event.invoiceId !== undefined) {
      addUnique(state.invoiceIds, event.invoiceId);
      state.lastInvoiceId = event.invoiceId;
    }
    if (event.periodStart !== undefined) {
      state.lastPeriodStart = event.periodStart;
    }
    if (event.periodEnd !== undefined) {
      state.lastPeriodEnd = event.periodEnd;
    }
    if (event.mergeFromAccountId !== undefined) {
      addUnique(state.mergedFromAccountIds, event.mergeFromAccountId);
    }

    state.lastEventAt = event.effectiveAt;
  }

  return [...states.values()].sort((a, b) => a.accountId.localeCompare(b.accountId));
}

export function evaluateEntitlements(state: AccountState, asOf?: string): EntitlementState {
  const plan = PLAN_DEFINITIONS[state.plan];
  const couponActive =
    state.status !== "closed" &&
    state.couponCode !== null &&
    state.couponExpiresAt !== null &&
    (asOf === undefined || state.couponExpiresAt >= asOf);

  if (state.status === "closed") {
    return {
      active: false,
      features: [],
      usageLimit: 0,
      overLimit: state.usage > 0,
      couponActive: false
    };
  }

  return {
    active: state.status === "active" || state.status === "past_due",
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
    currency: state.currency,
    seats: state.seats,
    couponCode: state.couponCode,
    couponActive: entitlements.couponActive,
    invoiceIds: [...state.invoiceIds],
    lastInvoiceId: state.lastInvoiceId,
    lastPeriodStart: state.lastPeriodStart,
    lastPeriodEnd: state.lastPeriodEnd,
    mergedFromAccountIds: [...state.mergedFromAccountIds],
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
    "currency",
    "seats",
    "usage",
    "usage_limit",
    "over_limit",
    "coupon_code",
    "coupon_active",
    "invoice_ids",
    "last_invoice_id",
    "last_period_start",
    "last_period_end",
    "merged_from_account_ids",
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
      summary.currency ?? "",
      String(summary.seats),
      String(summary.usage),
      String(summary.usageLimit),
      String(summary.overLimit),
      summary.couponCode ?? "",
      String(summary.couponActive),
      summary.invoiceIds.join("|"),
      summary.lastInvoiceId ?? "",
      summary.lastPeriodStart ?? "",
      summary.lastPeriodEnd ?? "",
      summary.mergedFromAccountIds.join("|"),
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

function readOptionalString(raw: RawEvent, field: string, issues: string[]): string | undefined {
  if (raw[field] === undefined) {
    return undefined;
  }
  const value = raw[field];
  if (typeof value !== "string") {
    issues.push(`invalid_${field}`);
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

  const trimmed = value.trim();
  const date = new Date(hasTimezone(trimmed) ? trimmed : `${trimmed}Z`);
  if (Number.isNaN(date.getTime())) {
    issues.push(issueCode);
    return null;
  }

  return date.toISOString();
}

function normalizeOptionalTimestamp(
  raw: RawEvent,
  field: string,
  issues: string[],
  issueCode: string
): string | null | undefined {
  if (raw[field] === undefined) {
    return undefined;
  }
  const value = readOptionalString(raw, field, issues);
  if (value === undefined) {
    return null;
  }
  return normalizeTimestamp(value, issues, issueCode);
}

function copyOptionalTimestamp(
  raw: RawEvent,
  normalized: NormalizedEvent,
  rawField: string,
  normalizedField: "periodStart" | "periodEnd",
  issues: string[],
  issueCode: string
): void {
  const value = normalizeOptionalTimestamp(raw, rawField, issues, issueCode);
  if (value !== undefined && value !== null) {
    normalized[normalizedField] = value;
  }
}

function readOptionalInteger(
  raw: RawEvent,
  field: string,
  issues: string[],
  issueCode: string,
  options: { min?: number; defaultValue?: number } = {}
): number | undefined {
  if (raw[field] === undefined) {
    return options.defaultValue;
  }
  const value = readIntegerValue(raw[field], options);
  if (value === null) {
    issues.push(issueCode);
    return options.defaultValue;
  }
  return value;
}

function readIntegerValue(value: unknown, options: { min?: number } = {}): number | null {
  if (typeof value !== "number" || !Number.isInteger(value)) {
    return null;
  }
  if (options.min !== undefined && value < options.min) {
    return null;
  }
  return value;
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

function normalizeCurrency(value: unknown): string | null | undefined {
  if (value === undefined) {
    return undefined;
  }
  if (typeof value !== "string") {
    return null;
  }
  const trimmed = value.trim().toUpperCase();
  if (!/^[A-Z]{3}$/.test(trimmed)) {
    return null;
  }
  return trimmed;
}

function copyOptionalId(
  raw: RawEvent,
  normalized: NormalizedEvent,
  rawField: string,
  normalizedField: "mergeFromAccountId" | "correctionOf" | "voidedEventId" | "invoiceId",
  issues: string[]
): void {
  const value = readOptionalString(raw, rawField, issues);
  if (value !== undefined) {
    normalized[normalizedField] = value;
  }
}

function compareReplayOrder(a: NormalizedEvent, b: NormalizedEvent): number {
  return (
    a.effectiveAt.localeCompare(b.effectiveAt) ||
    a.recordedAt.localeCompare(b.recordedAt) ||
    a.sequence - b.sequence ||
    a.id.localeCompare(b.id)
  );
}

function addUnique(values: string[], value: string): void {
  if (!values.includes(value)) {
    values.push(value);
  }
}

function hasTimezone(value: string): boolean {
  return /(?:Z|[+-]\d{2}:\d{2})$/i.test(value);
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
    currency: null,
    seats: 1,
    couponCode: null,
    couponExpiresAt: null,
    invoiceIds: [],
    lastInvoiceId: null,
    lastPeriodStart: null,
    lastPeriodEnd: null,
    mergedFromAccountIds: [],
    closedAt: null,
    lastEventAt: null
  };
  states.set(accountId, state);
  return state;
}
