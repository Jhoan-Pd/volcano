import type { CSSProperties } from "react";

/**
 * Título que entra palabra por palabra desde una máscara (cada palabra sube desde abajo).
 * El texto completo queda en aria-label para que los lectores de pantalla lo lean de corrido.
 */
export default function TituloRevelado({ texto, className = "", retraso = 0, paso = 60 }: {
  texto: string; className?: string; retraso?: number; paso?: number;
}) {
  const palabras = texto.split(/\s+/).filter(Boolean);
  return (
    <h1 className={className} aria-label={texto}>
      {palabras.map((p, i) => (
        // key con el texto: si cambia el municipio, la animación vuelve a correr
        <span key={`${texto}-${i}`} aria-hidden className="mascara" style={{ "--retraso": `${retraso + i * paso}ms` } as CSSProperties}>
          <span>{p}</span>{i < palabras.length - 1 ? " " : ""}
        </span>
      ))}
    </h1>
  );
}
