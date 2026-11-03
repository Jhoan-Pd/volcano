"use client";

import { useEffect, useState } from "react";

/**
 * Cuadros por segundo del hilo principal, medidos con requestAnimationFrame. Sirve para
 * demostrar que un Web Worker trabaja sin congelar la página: si el cálculo corriera aquí,
 * los fps caerían a casi cero mientras dura.
 */
export function useFps(activo: boolean) {
  const [fps, setFps] = useState<number | null>(null);
  useEffect(() => {
    if (!activo) { setFps(null); return; }
    let cuadros = 0;
    let inicio = performance.now();
    let id = requestAnimationFrame(function paso(ahora) {
      cuadros++;
      if (ahora - inicio >= 500) {
        setFps(Math.round((cuadros * 1000) / (ahora - inicio)));
        cuadros = 0;
        inicio = ahora;
      }
      id = requestAnimationFrame(paso);
    });
    return () => cancelAnimationFrame(id);
  }, [activo]);
  return fps;
}
