"use client";

/**
 * Estado de la API compartido por toda la app (patrón observable mínimo + useSyncExternalStore).
 *
 * El backend corre en el plan gratis de Render: tras 15 minutos sin tráfico se duerme y la
 * primera petición tarda cerca de un minuto en despertarlo. Antes la página se quedaba en
 * blanco hasta fallar por tiempo; ahora un único sondeo a /health (no uno por componente)
 * detecta el arranque, la interfaz lo muestra y, al responder la API, avisa con el evento
 * `servidor-listo` para que las vistas que fallaron vuelvan a pedir sus datos solas.
 */
import { useSyncExternalStore } from "react";
import { API_BASE } from "@/api/cliente";

export type Fase = "comprobando" | "despertando" | "listo" | "caido";
export interface EstadoServidor { fase: Fase; desde: number; intentos: number }

export const EVENTO_LISTO = "servidor-listo";
const AVISO_TRAS_MS = 2_500;   // si /health no responde en este tiempo, se avisa que está despertando
const TIMEOUT_MS = 8_000;      // cada intento de /health
const PAUSA_MS = 4_000;        // entre intentos
const LIMITE_MS = 180_000;     // tras 3 minutos se da por caído (con botón para reintentar)

let estado: EstadoServidor = { fase: "comprobando", desde: Date.now(), intentos: 0 };
const oyentes = new Set<() => void>();
let enCurso = false;

function publicar(parcial: Partial<EstadoServidor>) {
  estado = { ...estado, ...parcial };
  oyentes.forEach((o) => o());
}

async function salud(): Promise<boolean> {
  try {
    const r = await fetch(`${API_BASE}/health`, { cache: "no-store", signal: AbortSignal.timeout(TIMEOUT_MS) });
    return r.ok; // la página de "Application loading" de Render responde 503 (y sin CORS)
  } catch {
    return false;
  }
}

/** Sondea /health hasta que responda. Idempotente: varias llamadas comparten el mismo sondeo. */
export async function vigilarServidor(): Promise<void> {
  if (enCurso || estado.fase === "listo") return;
  enCurso = true;
  const inicio = Date.now();
  publicar({ fase: "comprobando", desde: inicio, intentos: 0 });
  const aviso = setTimeout(() => { if (estado.fase === "comprobando") publicar({ fase: "despertando" }); }, AVISO_TRAS_MS);
  try {
    for (let intento = 1; Date.now() - inicio < LIMITE_MS; intento++) {
      publicar({ intentos: intento });
      if (await salud()) {
        const estabaDormido = estado.fase === "despertando";
        publicar({ fase: "listo" });
        if (estabaDormido) window.dispatchEvent(new Event(EVENTO_LISTO));
        return;
      }
      if (estado.fase === "comprobando") publicar({ fase: "despertando" });
      await new Promise((r) => setTimeout(r, PAUSA_MS));
    }
    publicar({ fase: "caido" });
  } finally {
    clearTimeout(aviso);
    enCurso = false;
  }
}

/** Una petición falló sin respuesta (red o tiempo agotado): puede que la API se haya dormido. */
export function reportarFalloDeRed() {
  if (estado.fase === "listo") estado = { ...estado, fase: "comprobando" };
  void vigilarServidor();
}

function suscribir(oyente: () => void) {
  oyentes.add(oyente);
  return () => { oyentes.delete(oyente); };
}

const INICIAL: EstadoServidor = { fase: "comprobando", desde: 0, intentos: 0 };

export function useEstadoServidor(): EstadoServidor {
  return useSyncExternalStore(suscribir, () => estado, () => INICIAL);
}
