/**
 * Peticiones a la API desde el SERVIDOR de Next.js (componentes de servidor, build e ISR).
 *
 * Cada página elige su estrategia de caché, y esa elección es justamente el patrón de rendering:
 *   - SSG  → `{ cache: "force-cache" }`        se pide una vez, en el build
 *   - ISR  → `{ revalidar: 3600, etiquetas }`  se guarda y se vuelve a pedir como máximo cada hora
 *   - SSR  → `{ cache: "no-store" }`           se pide en cada visita
 * En CSR la petición la hace el navegador (axios en api/servicios.ts), no este módulo.
 */
import { API_V1 } from "@/api/cliente";

export class ErrorApi extends Error {
  constructor(public estado: number, mensaje: string) {
    super(mensaje);
  }
}

interface Opciones {
  /** Segundos de ISR. `false` = no volver a pedir (contenido del build). */
  revalidar?: number | false;
  cache?: RequestCache;
  etiquetas?: string[];
  /** Render (plan gratis) tarda hasta ~50 s en despertar. */
  timeoutMs?: number;
}

export async function pedir<T>(ruta: string, params: Record<string, string | number | boolean | undefined | null> = {},
  { revalidar, cache, etiquetas, timeoutMs = 55_000 }: Opciones = {}): Promise<T> {
  const url = new URL(`${API_V1}${ruta}`);
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
  const next = revalidar !== undefined || etiquetas ? { revalidate: revalidar, tags: etiquetas } : undefined;
  const r = await fetch(url, { cache, next, signal: AbortSignal.timeout(timeoutMs), headers: { Accept: "application/json" } });
  if (!r.ok) {
    let mensaje = `Error ${r.status} en ${ruta}`;
    try {
      const cuerpo = await r.json();
      mensaje = cuerpo?.error?.mensaje ?? mensaje;
    } catch { /* cuerpo vacío */ }
    throw new ErrorApi(r.status, mensaje);
  }
  return r.json() as Promise<T>;
}

/** Igual que `pedir`, pero devuelve `null` en lugar de lanzar (para datos opcionales). */
export async function pedirOpcional<T>(...args: Parameters<typeof pedir>): Promise<T | null> {
  try {
    return await pedir<T>(...args);
  } catch {
    return null;
  }
}

/** Momento exacto en que el servidor generó el HTML (lo muestra el panel del patrón). */
export const ahoraIso = () => new Date().toISOString();
