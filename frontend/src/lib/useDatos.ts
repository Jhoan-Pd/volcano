"use client";

import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import axios from "axios";
import { mensajeError } from "../api/cliente";
import { EVENTO_LISTO, reportarFalloDeRed } from "./estadoServidor";

export interface Datos<T> {
  datos: T | null;
  error: string | null;
  cargando: boolean;
  recargar: () => void;
}

/**
 * Carga datos asíncronos y expone { datos, error, cargando, recargar }.
 *
 * Reemplaza el patrón repetido useEffect + varios useState + .then/.catch, y corrige su
 * condición de carrera: si el usuario cambia rápido de municipio, una respuesta vieja que
 * llegue tarde se descarta en lugar de pisar la nueva.
 * Si `cargar` es null (faltan datos previos, p. ej. aún no hay municipio) no hace nada.
 * `recargar()` vuelve a pedir los datos conservando los actuales mientras llegan (sin parpadeo).
 */
export function useDatos<T>(cargar: (() => Promise<T>) | null, deps: DependencyList): Datos<T> {
  const [estado, setEstado] = useState<{ datos: T | null; error: string | null; cargando: boolean }>(
    { datos: null, error: null, cargando: cargar != null });
  const [version, setVersion] = useState(0);
  const versionAnterior = useRef(version);

  useEffect(() => {
    const esRecarga = versionAnterior.current !== version;
    versionAnterior.current = version;
    if (!cargar) {
      setEstado({ datos: null, error: null, cargando: false });
      return;
    }
    let vigente = true;
    setEstado((e) => ({ datos: esRecarga ? e.datos : null, error: null, cargando: true }));
    cargar()
      .then((datos) => { if (vigente) setEstado({ datos, error: null, cargando: false }); })
      .catch((e) => {
        // Sin respuesta (red o tiempo agotado): probablemente la API está despertando
        if (axios.isAxiosError(e) && !e.response) reportarFalloDeRed();
        if (vigente) setEstado({ datos: null, error: mensajeError(e), cargando: false });
      });
    return () => { vigente = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- las dependencias las define quien llama
  }, [...deps, version]);

  const recargar = useCallback(() => setVersion((v) => v + 1), []);

  // Si la carga falló mientras el servidor dormía, se reintenta sola apenas despierta
  const hayError = estado.error != null;
  useEffect(() => {
    if (!hayError) return;
    window.addEventListener(EVENTO_LISTO, recargar);
    return () => window.removeEventListener(EVENTO_LISTO, recargar);
  }, [hayError, recargar]);

  return { ...estado, recargar };
}
