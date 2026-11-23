// Request IDs for the demo data. crypto.randomUUID() exists only in secure contexts (https or
// localhost). Opening the app over a LAN address such as http://192.168.x.x:3000 leaves it undefined,
// so this falls back to crypto.getRandomValues(), which works in every context.
export function newRequestId(): string {
  const c = globalThis.crypto;
  if (typeof c.randomUUID === "function") return c.randomUUID();
  const b = new Uint8Array(16);
  c.getRandomValues(b);
  b[6] = (b[6] & 0x0f) | 0x40; // version 4
  b[8] = (b[8] & 0x3f) | 0x80; // RFC 4122 variant
  const h = Array.from(b, (x) => x.toString(16).padStart(2, "0")).join("");
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
