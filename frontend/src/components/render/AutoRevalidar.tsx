"use client";

import { useEffect } from "react";
import { revalidarAhora } from "@/app/acciones";

/**
 * Se incluye solo en la versión de respaldo de una página ISR (cuando la API no respondió al
 * generarla). Al montarse pide revalidar la ruta: la siguiente visita ya recibe la versión con datos.
 */
export function AutoRevalidar({ ruta }: { ruta: string }) {
  useEffect(() => { void revalidarAhora(ruta); }, [ruta]);
  return null;
}
