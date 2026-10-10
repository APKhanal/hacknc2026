import Link from "next/link";
import { notFound } from "next/navigation";
import { fetchBackend, RunNotFoundError } from "@/lib/backend";
import type { Customer, RunInputs, SimResult } from "@/lib/types";
import { AppShell } from "@/components/workspace/app-shell";
import { AeroPanel } from "@/components/ui/aero";
import { ReplayResult } from "@/components/workspace/replay-result";

export default async function ReplayPage({ params }: { params: Promise<{ run_id: string }> }) {
  const { run_id } = await params;
  const path = `run/${encodeURIComponent(run_id)}`;
  const [run, saved, profiles] = await Promise.allSettled([fetchBackend<SimResult>(path), fetchBackend<RunInputs>(`${path}/inputs`), fetchBackend<Customer[]>("customers")]);
  let result;
  try { if (run.status === "rejected") throw run.reason; result = run.value; }
  catch (error) {
    if (error instanceof RunNotFoundError) notFound();
    return <AppShell view="replays"><AeroPanel className="error-state"><h1>This replay could not load.</h1><p>The simulation service may be unavailable. Try again in a moment or open another replay.</p><Link href="/?view=replays">Back to replays</Link></AeroPanel></AppShell>;
  }
  return <ReplayResult result={result} inputs={saved.status === "fulfilled" ? saved.value : null} customers={profiles.status === "fulfilled" ? profiles.value : []} />;
}
