import { Workspace } from "@/components/workspace/workspace";
import type { WorkspaceView } from "@/components/workspace/app-shell";

export default async function Home({ searchParams }: { searchParams: Promise<{ view?: string }> }) {
  const { view } = await searchParams;
  const active: WorkspaceView | null = view === "overview" || view === "scenarios" || view === "replays" || view === "preferences" ? view : null;
  return <Workspace view={active} />;
}
