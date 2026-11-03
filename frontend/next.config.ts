import type { NextConfig } from "next";

// La URL de la API se lee de NEXT_PUBLIC_API_URL. Se acepta también VITE_API_URL (la variable
// que usaba la versión con Vite) para no romper el proyecto ya configurado en Vercel.
const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? process.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  env: { NEXT_PUBLIC_API_URL: API_URL },
  poweredByHeader: false,
  reactStrictMode: true,
};

export default nextConfig;
