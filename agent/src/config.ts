export interface AgentConfig {
  projectId: string;
  projectSecret: string;
  apiBaseUrl: string;
  replayBaseUrl: string;
  customerPhoneMap: Record<string, string>;
  askTimeoutMs: number;
  interimMessageAfterMs: number;
  interimMessageText?: string;
  enableReactionRerun: boolean;
}

function requireEnv(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`missing required env var ${name} (see .env.example)`);
  }
  return value;
}

export function loadConfig(): AgentConfig {
  const rawMap = process.env.CUSTOMER_PHONE_MAP ?? "{}";
  let customerPhoneMap: Record<string, string>;
  try {
    customerPhoneMap = JSON.parse(rawMap);
  } catch {
    throw new Error("CUSTOMER_PHONE_MAP is not valid JSON");
  }

  const interimMessageText = process.env.INTERIM_MESSAGE_TEXT?.trim();

  return {
    projectId: requireEnv("PROJECT_ID"),
    projectSecret: requireEnv("PROJECT_SECRET"),
    apiBaseUrl: requireEnv("API_BASE_URL"),
    replayBaseUrl: process.env.REPLAY_BASE_URL ?? "",
    customerPhoneMap,
    askTimeoutMs: Number(process.env.ASK_TIMEOUT_MS ?? 20000),
    interimMessageAfterMs: Number(process.env.INTERIM_MESSAGE_AFTER_MS ?? 8000),
    interimMessageText: interimMessageText || undefined,
    enableReactionRerun: process.env.ENABLE_REACTION_RERUN === "true",
  };
}

export function resolveCustomerId(
  map: Record<string, string>,
  phone: string | undefined
): string | undefined {
  if (!phone) return undefined;
  return map[phone];
}
