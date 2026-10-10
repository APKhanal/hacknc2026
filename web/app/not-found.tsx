import Link from "next/link";
import { AppShell } from "@/components/workspace/app-shell";
import { AeroPanel } from "@/components/ui/aero";

export default function NotFound() {
  return <AppShell view="overview"><AeroPanel className="error-state"><h1>This page is not here.</h1><p>Return to your workspace to start a draft or open a replay.</p><Link href="/">Back to your workspace</Link></AeroPanel></AppShell>;
}
