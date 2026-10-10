import type { SimResult } from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export function txnUrl(txnId: string): string {
  return `${API_BASE_URL}/txn/${encodeURIComponent(txnId)}`;
}

export class RunNotFoundError extends Error {}

export async function fetchRun(runId: string): Promise<SimResult> {
  const res = await fetch(`${API_BASE_URL}/run/${encodeURIComponent(runId)}`, {
    cache: "no-store",
  });

  if (res.status === 404) {
    throw new RunNotFoundError(`run ${runId} not found`);
  }
  if (!res.ok) {
    throw new Error(`GET /run/${runId} failed: ${res.status}`);
  }

  return res.json() as Promise<SimResult>;
}
