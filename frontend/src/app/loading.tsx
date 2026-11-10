/**
 * Se muestra mientras una página de servidor (SSR o una regeneración ISR) espera a la API.
 * Un esqueleto con la forma de la página evita el salto de contenido y deja claro que algo
 * está cargando; el aviso global de la cabecera explica si el servidor está despertando.
 */
function Bloque({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-lg bg-surface-2 ${className}`} />;
}

export default function Cargando() {
  return (
    <div className="space-y-6" role="status" aria-label="Cargando la página">
      <Bloque className="h-12 w-full" />
      <div className="space-y-3">
        <Bloque className="h-3 w-48" />
        <Bloque className="h-12 w-3/4 max-w-2xl" />
        <Bloque className="h-4 w-full max-w-3xl" />
      </div>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => <Bloque key={i} className="h-36" />)}
      </div>
      <Bloque className="h-72 w-full" />
      <span className="sr-only">Consultando la API…</span>
    </div>
  );
}
