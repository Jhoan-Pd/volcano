/** Utilidades para páginas SSR: leer parámetros de la URL y datos de la petición. */
import { headers } from "next/headers";

export type Busqueda = Record<string, string | string[] | undefined>;

export const texto = (v: string | string[] | undefined) => (Array.isArray(v) ? v[0] : v)?.trim() ?? "";
export const entero = (v: string | string[] | undefined) => {
  const n = Number.parseInt(texto(v), 10);
  return Number.isFinite(n) ? n : undefined;
};

function navegador(ua: string) {
  if (/edg\//i.test(ua)) return "Edge";
  if (/chrome\//i.test(ua)) return "Chrome";
  if (/firefox\//i.test(ua)) return "Firefox";
  if (/safari\//i.test(ua)) return "Safari";
  return ua ? "Otro" : "Desconocido";
}

/** Datos que solo existen en el momento de la visita: prueba de que la página es SSR. */
export async function datosDePeticion() {
  const h = await headers();
  return {
    navegador: navegador(h.get("user-agent") ?? ""),
    idioma: (h.get("accept-language") ?? "").split(",")[0] || "—",
    region: h.get("x-vercel-ip-country-region") ?? h.get("x-vercel-ip-country") ?? "local",
  };
}
