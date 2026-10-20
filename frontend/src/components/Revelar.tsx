import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode } from "react";

/** Devuelve true la primera vez que el elemento entra en pantalla (y se queda así). */
export function useVisible<T extends Element>(margen = "0px 0px -8% 0px") {
  const ref = useRef<T>(null);
  const [visible, setVisible] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || visible) return;
    if (typeof IntersectionObserver === "undefined") { setVisible(true); return; }
    const obs = new IntersectionObserver(([e]) => {
      if (e.isIntersecting) { setVisible(true); obs.disconnect(); }
    }, { rootMargin: margen, threshold: 0.05 });
    obs.observe(el);
    return () => obs.disconnect();
  }, [margen, visible]);
  return { ref, visible };
}

/**
 * Hace aparecer su contenido (sube 24 px y se vuelve opaco) cuando entra en pantalla.
 * `retraso` escalona varios elementos seguidos (p. ej. las tarjetas del semáforo).
 */
export default function Revelar({ children, retraso = 0, como: Etiqueta = "div", className = "" }: {
  children: ReactNode; retraso?: number; como?: ElementType; className?: string;
}) {
  const { ref, visible } = useVisible<HTMLElement>();
  return (
    <Etiqueta ref={ref} className={`revelar ${visible ? "visible" : ""} ${className}`}
      style={{ "--retraso": `${retraso}ms` } as CSSProperties}>
      {children}
    </Etiqueta>
  );
}
