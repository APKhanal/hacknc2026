import { screenshotExportCard } from "@/lib/screenshot";

export const dynamic = "force-dynamic";

export async function GET(request: Request, context: { params: Promise<{ run_id: string }> }) {
  const { run_id } = await context.params;
  const origin = new URL(request.url).origin;
  const result = await screenshotExportCard(origin, run_id, '[data-stats-card="true"]');
  if (result.status !== 200) {
    return Response.json({ detail: result.detail }, { status: result.status });
  }
  return new Response(new Uint8Array(result.body), {
    headers: { "Content-Type": "image/png", "Cache-Control": "no-store" },
  });
}
