// Single entry point for pages. Chooses demo or live data based on NEXT_PUBLIC_DATA_MODE.
import { liveAsk, liveCapabilities, liveHealth } from "./api";
import { IS_MOCK } from "./config";
import { MOCK_CAPABILITIES, MOCK_HEALTH, mockAsk } from "./mock";
import type { CapabilitiesResponse, ChatResponse, HealthResponse } from "./types";
import { getActiveUser } from "./users";

export function ask(message: string): Promise<ChatResponse> {
  // Demo only: the demo answers for the signed-in demo user's merchant. Live mode uses the token.
  return IS_MOCK ? mockAsk(message, getActiveUser().merchantId) : liveAsk(message);
}

export function getCapabilities(): Promise<CapabilitiesResponse> {
  return IS_MOCK ? Promise.resolve(MOCK_CAPABILITIES) : liveCapabilities();
}

export function getHealth(): Promise<HealthResponse> {
  return IS_MOCK ? Promise.resolve(MOCK_HEALTH) : liveHealth();
}
