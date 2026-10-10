import { notFound } from "next/navigation";
import { fetchRun, RunNotFoundError } from "@/lib/api";
import { Headline } from "@/components/Headline";
import { FanChart } from "@/components/FanChart";
import { CulpritPanel } from "@/components/CulpritPanel";
import { ProvenanceTable } from "@/components/ProvenanceTable";

export default async function ReplayPage({
  params,
}: {
  params: Promise<{ run_id: string }>;
}) {
  const { run_id } = await params;

  let result;
  try {
    result = await fetchRun(run_id);
  } catch (err) {
    if (err instanceof RunNotFoundError) {
      notFound();
    }
    return (
      <main className="page">
        <div className="error-page">
          <h1>Couldn&apos;t load this run</h1>
          <p className="muted">{(err as Error).message}</p>
        </div>
      </main>
    );
  }

  return (
    <main className="page">
      <Headline result={result} />

      <section className="fan-chart-section">
        <span className="section-eyebrow">
          {result.n_paths} simulated paths · {result.horizon_weeks} weeks
        </span>
        <FanChart paths={result.paths} breachThreshold={result.breach_threshold} />
      </section>

      <CulpritPanel culprit={result.culprit} />

      <ProvenanceTable claims={result.claims} />
    </main>
  );
}
