"use client";

import { Aviso, Boton } from "@/components/ui";

/** Límite de error de Next.js: si una página no pudo obtener sus datos se muestra esto en lugar de romper el sitio. */
export default function ErrorPagina({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="mx-auto max-w-xl space-y-3 py-10">
      <Aviso tipo="error">
        <p className="font-medium">No se pudo cargar esta página</p>
        <p className="mt-1">{error.message || "La API no respondió."}</p>
        <p className="mt-2 text-xs opacity-80">Si el backend está en Render (plan gratuito), puede tardar ~1 minuto en despertar.</p>
      </Aviso>
      <Boton onClick={reset}>Intentar de nuevo</Boton>
    </div>
  );
}
