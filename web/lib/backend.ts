// Server-side only: browsers use the same-origin /api/backend routes.
export const backendOrigin = () => (process.env.API_BASE_URL ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");
export class RunNotFoundError extends Error {}
export async function fetchBackend<T>(path: string): Promise<T> {
  const response = await fetch(`${backendOrigin()}/${path}`, { cache: "no-store", signal: AbortSignal.timeout(15000) });
  if (response.status === 404) throw new RunNotFoundError("Replay not found");
  if (!response.ok) throw new Error(`Simulation service returned ${response.status}`);
  return response.json() as Promise<T>;
}
