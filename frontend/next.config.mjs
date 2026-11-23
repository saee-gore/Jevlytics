/** @type {import('next').NextConfig} */
// The browser only talks to /api/backend/*. Next.js forwards those requests to the FastAPI server
// on the server side, so the browser never sees the backend URL and no CORS setup is needed.
const backendUrl = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  // Hides the Next.js dev-tools "N" button in the bottom-left corner (development only).
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/backend/:path*", destination: `${backendUrl}/:path*` }];
  },
  // Activity (with the AI Assistant) is the only page. Old URLs go there instead of showing removed pages.
  async redirects() {
    return ["/", "/assistant", "/analytics", "/capabilities", "/settings"].map((source) => ({
      source,
      destination: "/activity",
      permanent: false,
    }));
  },
};

export default nextConfig;
