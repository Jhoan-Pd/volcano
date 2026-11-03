"use client";

import { useEffect, useState } from "react";
import { API_V1 } from "@/api/cliente";
import { alertaApi } from "@/api/servicios";
import type { Alerta, AlertaMotor, EventoAlertaMotor, Nivel } from "@/api/tipos";

/** Alerta en la forma común a las dos fuentes (REST y stream del motor). */
export interface AlertaVista {
  id: number;
  municipio_id: number;
  municipio: string;
  enfermedad: string;
  semana: string;
  nivel: Nivel;
  origen: "OBSERVADO" | "PREDICHO";
  mensaje: string;
}

export type ModoConexion = "conectando" | "en-vivo" | "reconectando" | "consulta-periodica";

export interface CambioAlerta {
  tipo: EventoAlertaMotor["tipo"];
  momento: string;
  alerta: AlertaVista;
}

const desdeRest = (a: Alerta): AlertaVista => ({
  id: a.id, municipio_id: a.municipio_id, municipio: a.municipio, enfermedad: a.enfermedad, semana: a.etiqueta,
  nivel: a.nivel_riesgo, origen: a.origen, mensaje: a.mensaje,
});
const desdeMotor = (a: AlertaMotor): AlertaVista => ({ ...a, nivel: a.nivel ?? "NARANJA" });

const CONSULTA_MS = 5 * 60_000;

/**
 * Alertas activas que se actualizan solas.
 *
 * 1. Primero se piden por REST (/alertas/activas): la pantalla se llena enseguida.
 * 2. Luego se abre un EventSource hacia /motor/alertas/eventos. La API lo alimenta con el stream
 *    gRPC `SeguirAlertas` del motor: cada alerta NUEVA, ACTUALIZADA o CERRADA llega al instante.
 * 3. Si el motor no está disponible (evento `fallo`) se cierra el stream y se vuelve a la
 *    consulta periódica cada 5 minutos. Si solo se corta la red, EventSource reintenta solo.
 */
export function useAlertasEnVivo(municipioId?: number) {
  const [alertas, setAlertas] = useState<Map<number, AlertaVista>>(new Map());
  const [modo, setModo] = useState<ModoConexion>("conectando");
  const [cambios, setCambios] = useState<CambioAlerta[]>([]);
  const [actualizadoEn, setActualizadoEn] = useState<string | null>(null);

  useEffect(() => {
    let vigente = true;
    let intervalo: number | undefined;
    const filtrar = (xs: AlertaVista[]) => (municipioId ? xs.filter((a) => a.municipio_id === municipioId) : xs);

    const consultar = () => alertaApi.activas()
      .then((xs) => {
        if (!vigente) return;
        setAlertas(new Map(filtrar(xs.map(desdeRest)).map((a) => [a.id, a])));
        setActualizadoEn(new Date().toISOString());
      })
      .catch(() => undefined);

    const aConsultaPeriodica = () => {
      setModo("consulta-periodica");
      if (intervalo === undefined) intervalo = window.setInterval(consultar, CONSULTA_MS);
    };

    consultar();
    if (typeof EventSource === "undefined") {
      aConsultaPeriodica();
      return () => { vigente = false; window.clearInterval(intervalo); };
    }

    const url = `${API_V1}/motor/alertas/eventos${municipioId ? `?municipio_id=${municipioId}` : ""}`;
    const fuente = new EventSource(url);
    fuente.onopen = () => setModo("en-vivo");
    fuente.addEventListener("alerta", (e) => {
      const ev = JSON.parse((e as MessageEvent<string>).data) as EventoAlertaMotor;
      const alerta = desdeMotor(ev.alerta);
      setModo("en-vivo");
      setActualizadoEn(ev.momento);
      setAlertas((previas) => {
        const nuevas = new Map(previas);
        if (ev.tipo === "CERRADA") nuevas.delete(alerta.id);
        else nuevas.set(alerta.id, alerta);
        return nuevas;
      });
      if (ev.tipo !== "ACTIVA") setCambios((cs) => [{ tipo: ev.tipo, momento: ev.momento, alerta }, ...cs].slice(0, 20));
    });
    fuente.addEventListener("fallo", () => { // el motor gRPC no responde: no tiene sentido reintentar cada 5 s
      fuente.close();
      aConsultaPeriodica();
    });
    fuente.onerror = () => {
      if (fuente.readyState === EventSource.CLOSED) aConsultaPeriodica();
      else setModo((m) => (m === "consulta-periodica" ? m : "reconectando"));
    };

    return () => {
      vigente = false;
      fuente.close();
      window.clearInterval(intervalo);
    };
  }, [municipioId]);

  return { alertas: [...alertas.values()], modo, cambios, actualizadoEn };
}
