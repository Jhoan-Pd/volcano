import { useEffect, useRef, useState } from "react";

const salida = (t: number) => 1 - Math.pow(1 - t, 5); // ease-out quint

/** Anima un número desde su valor anterior (o 0) hasta `valor` cuando `activo` es true. */
export function useContador(valor: number, activo = true, duracion = 900): number {
  const [actual, setActual] = useState(0);
  const desde = useRef(0);
  useEffect(() => {
    if (!activo) return;
    const reducir = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (reducir) { setActual(valor); desde.current = valor; return; }
    const inicio = performance.now();
    const origen = desde.current;
    let id = 0;
    const paso = (t: number) => {
      const p = Math.min(1, (t - inicio) / duracion);
      setActual(origen + (valor - origen) * salida(p));
      if (p < 1) id = requestAnimationFrame(paso);
      else desde.current = valor;
    };
    id = requestAnimationFrame(paso);
    return () => cancelAnimationFrame(id);
  }, [valor, activo, duracion]);
  return actual;
}
