import "dotenv/config";
import { Spectrum, Emoji, type Space } from "spectrum-ts";
import { imessage } from "spectrum-ts/providers/imessage";
import { loadConfig, resolveCustomerId } from "./config.js";
import { askOrchestrator, resolveReplayUrl, AskTimeoutError } from "./askClient.js";

const config = loadConfig();

const app = await Spectrum({
  projectId: config.projectId,
  projectSecret: config.projectSecret,
  providers: [imessage.config()],
});

console.log("counterfactual agent listening for iMessages...");

// Tracks our own outbound result messages so a thumbs-up reaction can
// re-run /ask with the decision applied. In-memory only, lost on restart —
// fine for a hackathon demo (see ENABLE_REACTION_RERUN in .env.example).
const pendingReruns = new Map<string, { text: string; customerId: string }>();

async function handleAsk(space: Space, text: string, customerId: string): Promise<void> {
  await space.startTyping();

  // Typing indicators aren't guaranteed to hold indefinitely, and a bare
  // thread going quiet reads as broken on stage. Refresh it, and optionally
  // fire one interim message, while we wait on the orchestrator.
  const keepAlive = setInterval(() => {
    space.startTyping().catch(() => {});
  }, 8000);

  let interimTimer: NodeJS.Timeout | undefined;
  if (config.interimMessageText) {
    interimTimer = setTimeout(() => {
      space.send(config.interimMessageText!).catch(() => {});
    }, config.interimMessageAfterMs);
  }

  try {
    const result = await askOrchestrator(config.apiBaseUrl, text, customerId, config.askTimeoutMs);
    const replayUrl = resolveReplayUrl(result, config.replayBaseUrl);

    const sent = await space.send(result.prose);
    await space.send(replayUrl);

    if (config.enableReactionRerun && sent?.id) {
      pendingReruns.set(sent.id, { text, customerId });
    }
  } catch (err) {
    const message =
      err instanceof AskTimeoutError
        ? "That's taking longer than it should — give it another shot in a bit."
        : "Hit a snag running the numbers just now — try asking again.";
    console.error("ask failed:", err);
    await space.send(message);
  } finally {
    if (interimTimer) clearTimeout(interimTimer);
    clearInterval(keepAlive);
    await space.stopTyping();
  }
}

for await (const [space, message] of app.messages) {
  if (message.direction !== "inbound") continue;

  if (message.content.type === "reaction") {
    if (!config.enableReactionRerun) continue;
    if (message.content.emoji !== Emoji.thumbsUp) continue;

    const pending = pendingReruns.get(message.content.target.id);
    if (!pending) continue;

    await handleAsk(space, `${pending.text} (assume I go ahead with it)`, pending.customerId);
    continue;
  }

  if (message.content.type !== "text") continue;

  const customerId = resolveCustomerId(config.customerPhoneMap, message.sender?.id);
  if (!customerId) {
    await space.send(
      "This number isn't linked to an account yet — ask whoever's running the demo to add it."
    );
    continue;
  }

  await handleAsk(space, message.content.text, customerId);
}
