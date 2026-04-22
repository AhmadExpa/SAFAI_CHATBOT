// Backend API Configuration
export const API_BASE_URL = (() => {
  const envValue = (import.meta.env.VITE_API_BASE_URL || "")
    .trim()
    .replace(/\/$/, "");

  if (typeof window !== "undefined") {
    const isLocalhost = window.location.hostname.includes("localhost") ||
      window.location.hostname === "127.0.0.1";

    // If we are NOT on localhost (i.e. on Vercel)
    if (!isLocalhost) {
      // Vercel serves the frontend and backend on the same origin here.
      // The API already has mixed route prefixes (/auth, /api, /openai, etc.),
      // so a base of "/api" would create broken URLs like "/api/api/projects".
      if (!envValue || envValue.includes("localhost") || envValue === "/api") {
        return "";
      }
    } else {
      // If we ARE on localhost, default to local backend port if no env is set
      return envValue || "http://localhost:8000";
    }
  }

  return envValue || "";
})();

export const config = {
  apiBaseUrl: API_BASE_URL,
  appName: import.meta.env.VITE_APP_NAME || "Safai",
};

export default config;
