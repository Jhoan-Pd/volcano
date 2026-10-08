import axios, { AxiosError } from "axios";

const BASE = (import.meta.env.VITE_API_URL ?? "http://localhost:8000").replace(/\/$/, "");

export const api = axios.create({
  baseURL: `${BASE}/api/v1`,
  timeout: 60_000, // Render (plan gratis) puede tardar ~50 s en "despertar"
});

const CLAVE_TOKEN = "token";

export function guardarToken(token: string | null) {
  try {
    if (token) localStorage.setItem(CLAVE_TOKEN, token);
    else localStorage.removeItem(CLAVE_TOKEN);
  } catch {
    /* almacenamiento no disponible */
  }
}

export function leerToken(): string | null {
  try {
    return localStorage.getItem(CLAVE_TOKEN);
  } catch {
    return null;
  }
}

// Adjunta el JWT a cada petición
api.interceptors.request.use((config) => {
  const token = leerToken();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Si el token expiró, se limpia la sesión y se avisa a la app
api.interceptors.response.use(
  (r) => r,
  (error: AxiosError) => {
    if (error.response?.status === 401 && leerToken()) {
      guardarToken(null);
      window.dispatchEvent(new Event("sesion-expirada"));
    }
    return Promise.reject(error);
  },
);

interface ErrorApi {
  error?: { codigo: string; mensaje: string; detalles?: { campo: string; mensaje: string }[] | null };
}

/** Convierte cualquier error de Axios en un mensaje legible en español. */
export function mensajeError(e: unknown): string {
  if (axios.isAxiosError(e)) {
    const data = e.response?.data as ErrorApi | undefined;
    if (data?.error) {
      const det = data.error.detalles;
      if (Array.isArray(det) && det.length) {
        return det.map((d) => (d.campo ? `${d.campo}: ${d.mensaje}` : d.mensaje)).join(" · ");
      }
      return data.error.mensaje;
    }
    if (e.code === "ECONNABORTED") return "El servidor tardó demasiado en responder. Intenta de nuevo.";
    if (!e.response) return "No se pudo conectar con el servidor. Revisa tu conexión o la URL de la API.";
    return `Error ${e.response.status}`;
  }
  return e instanceof Error ? e.message : "Error desconocido";
}
