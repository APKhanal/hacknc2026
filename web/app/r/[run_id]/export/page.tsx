import { notFound } from "next/navigation";
import { fetchBackend, RunNotFoundError } from "@/lib/backend";
import type { SimResult } from "@/lib/types";
import { GraphCard, StatsCard } from "@/components/workspace/export-cards";

// Minimal, non-interactive view used only for server-side screenshotting
// (see app/api/chart/[run_id] and app/api/stats/[run_id]) - deliberately not
// part of the interactive desktop workspace, so a captured PNG never
// includes chrome (sliders, tabs, window controls) that doesn't make sense
// as a static image.
export default async function ExportPage({ params }: { params: Promise<{ run_id: string }> }) {
  const { run_id } = await params;
  let result: SimResult;
  try {
    result = await fetchBackend<SimResult>(`run/${encodeURIComponent(run_id)}`);
  } catch (error) {
    if (error instanceof RunNotFoundError) notFound();
    throw error;
  }
  return (
    <div style={{ display: "inline-flex", flexDirection: "column", gap: 20, padding: 24 }}>
      <StatsCard result={result} />
      <GraphCard result={result} />
    </div>
  );
}
