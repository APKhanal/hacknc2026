import Link from "next/link";
import { AppShell } from "@/components/workspace/app-shell";
import { AeroPanel } from "@/components/ui/aero";

export default function RunNotFound() {
  return <AppShell view="replays"><AeroPanel className="error-state"><h1>That replay is not here.</h1><p>No simulation matches this ID. Check the ID from your simulation response and try again.</p><Link href="/?view=replays">Back to replays</Link></AeroPanel></AppShell>;
}
