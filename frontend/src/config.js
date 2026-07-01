// Centralized API base URL.
// Override at build time with the VITE_API_URL environment variable
// (e.g. in a .env file or your Vercel project settings).
export const API_BASE =
  import.meta.env.VITE_API_URL || "https://blai-dwb1.onrender.com";
