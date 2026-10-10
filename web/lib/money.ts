import type { TxnRecord } from "./types";

/** Evidence is raw: only its saved unit determines whether conversion is needed. */
export function evidenceAmount(record: TxnRecord, unit?: string): number | null {
  const raw = record.amount ?? record.payment_amount;
  if ((unit !== "usd" && unit !== "usd_cents") || typeof raw !== "number" || !Number.isFinite(raw)) return null;
  return raw / (unit === "usd_cents" ? 100 : 1);
}
