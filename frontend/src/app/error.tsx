"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Aviso, Boton } from "@/components/ui";
import { EVENTO_LISTO, reportarFalloDeRed } from "@/lib/estadoServidor";

/** Límite de error de Next.js: si una página no pudo obtener sus datos se muestra esto en lugar de
 *  romper el sitio. Si la causa fue que la API dormía, la página se vuelve a pedir sola al despertar. */
export default function ErrorPagina({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  const router = useRouter();

  useEffect(() => {
    reportarFalloDeRed();
    const reintentar = () => { router.refresh(); reset(); };
    window.addEventListener(EVENTO_LISTO, reintentar);
    return () => window.removeEventListener(EVENTO_LISTO, reintentar);
  }, [router, reset]);

  return (
    <div className="mx-auto max-w-xl space-y-3 py-10">
      <Aviso tipo="error">
        <p className="font-medium">No se pudo cargar esta página</p>
        <p className="mt-1">{error.digest ? "La API no respondió a tiempo." : error.message || "La API no respondió."}</p>
        <p className="mt-2 text-xs opacity-80">Si el servidor estaba dormido, esta página se recarga sola cuando responda.</p>
      </Aviso>
      <Boton onClick={() => { router.refresh(); reset(); }}>Intentar de nuevo</Boton>
    </div>
  );
}
