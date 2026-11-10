"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { urlSimulador } from "@/api/servicios";
import type { Escenario, ResultadoEscenario } from "@/api/tipos";
import { EVENTO_LISTO, reportarFalloDeRed } from "@/lib/estadoServidor";

const MAX_REINTENTOS = 8;
const ESPERA_MAX_MS = 15_000;

/** Espera antes del reintento n (backoff exponencial con algo de azar para no reconectar todos a la vez). */
const espera = (n: number) => Math.min(ESPERA_MAX_MS, 1000 * 2 ** n) * (0.75 + Math.random() * 0.5);

export type EstadoSocket = "conectando" | "abierto" | "cerrado";

/**
 * Conversación con el simulador por WebSocket: del lado de la API es un stream BIDIRECCIONAL
 * de gRPC (SimularEscenarios). Cada cambio de un control envía un escenario y el resultado
 * llega en cuanto el motor lo calcula; no hay que esperar una respuesta para enviar el
 * siguiente. Se mide la ida y vuelta de cada mensaje y se ignoran las respuestas viejas.
 *
 * Si la conexión se cae (el servidor se durmió, se redesplegó o el celular cambió de red) se
 * reconecta sola con backoff exponencial y, al volver, la vista reenvía el escenario actual.
 */
export function useSimulador() {
  const ws = useRef<WebSocket | null>(null);
  const enviadosEn = useRef(new Map<string, number>());
  const ultimoId = useRef<string | null>(null);
  const [estado, setEstado] = useState<EstadoSocket>("conectando");
  const [resultado, setResultado] = useState<ResultadoEscenario | null>(null);
  const [recibidoEn, setRecibidoEn] = useState<string | null>(null);
  const [idaVueltaMs, setIdaVueltaMs] = useState<number | null>(null);
  const [cuenta, setCuenta] = useState({ enviados: 0, recibidos: 0 });
  const [error, setError] = useState<string | null>(null);
  const [intento, setIntento] = useState(0);
  const fallos = useRef(0);

  useEffect(() => {
    const socket = new WebSocket(urlSimulador());
    ws.current = socket;
    let cerradoPorNosotros = false;
    let temporizador: ReturnType<typeof setTimeout> | undefined;
    setEstado("conectando");
    socket.onopen = () => { fallos.current = 0; setEstado("abierto"); setError(null); };
    socket.onclose = () => {
      setEstado("cerrado");
      if (cerradoPorNosotros) return;
      reportarFalloDeRed();
      if (fallos.current < MAX_REINTENTOS) {
        temporizador = setTimeout(() => setIntento((n) => n + 1), espera(fallos.current));
        fallos.current += 1;
      } else {
        setError("No se pudo conectar con el simulador (WebSocket).");
      }
    };
    socket.onmessage = (e) => {
      const r = JSON.parse(e.data as string) as ResultadoEscenario;
      setCuenta((c) => ({ ...c, recibidos: c.recibidos + 1 }));
      if (r.fatal) { setError(r.error); return; }
      const enviado = r.id ? enviadosEn.current.get(r.id) : undefined;
      if (r.id) enviadosEn.current.delete(r.id);
      if (r.id !== ultimoId.current) return; // llegó la respuesta de un escenario que ya se reemplazó
      if (enviado) setIdaVueltaMs(Math.round(performance.now() - enviado));
      setResultado(r);
      setRecibidoEn(new Date().toISOString());
    };
    return () => { cerradoPorNosotros = true; clearTimeout(temporizador); socket.close(); };
  }, [intento]);

  // Cuando la API termina de despertar se reconecta de inmediato, sin esperar el backoff
  useEffect(() => {
    const ahora = () => { fallos.current = 0; setIntento((n) => n + 1); };
    window.addEventListener(EVENTO_LISTO, ahora);
    return () => window.removeEventListener(EVENTO_LISTO, ahora);
  }, []);

  const enviar = useCallback((escenario: Omit<Escenario, "id">) => {
    const socket = ws.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) return false;
    const id = `e${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
    ultimoId.current = id;
    enviadosEn.current.set(id, performance.now());
    socket.send(JSON.stringify({ ...escenario, id }));
    setCuenta((c) => ({ ...c, enviados: c.enviados + 1 }));
    return true;
  }, []);

  const reconectar = useCallback(() => { fallos.current = 0; setError(null); setIntento((n) => n + 1); }, []);

  return { estado, resultado, recibidoEn, idaVueltaMs, cuenta, error, enviar, reconectar };
}
