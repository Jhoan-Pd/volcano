import { Download, FileSpreadsheet, FileText, LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { mensajeError } from "../../api/cliente";
import { reporteApi } from "../../api/servicios";

/** Botón "Descargar" con el PDF del municipio y los CSV de datos. */
export default function MenuReportes({ municipioId, municipio, enfermedadId }: {
  municipioId: number; municipio: string; enfermedadId: number | null;
}) {
  const [abierto, setAbierto] = useState(false);
  const [cargando, setCargando] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const caja = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!abierto) return;
    const fuera = (e: MouseEvent) => { if (!caja.current?.contains(e.target as Node)) setAbierto(false); };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setAbierto(false);
    document.addEventListener("mousedown", fuera);
    document.addEventListener("keydown", esc);
    return () => { document.removeEventListener("mousedown", fuera); document.removeEventListener("keydown", esc); };
  }, [abierto]);

  async function bajar(id: string, fn: () => Promise<void>) {
    setCargando(id); setError(null);
    try {
      await fn();
      setAbierto(false);
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCargando(null);
    }
  }

  const opciones = [
    { id: "pdf", icono: <FileText size={15} />, titulo: `Reporte PDF de ${municipio}`, detalle: "Semáforo, predicción, alertas, volcán y modelos",
      fn: () => reporteApi.pdfMunicipio(municipioId) },
    { id: "casos", icono: <FileSpreadsheet size={15} />, titulo: "Casos semanales (CSV)", detalle: `${municipio}, enfermedad seleccionada`,
      fn: () => reporteApi.casosCsv(municipioId, enfermedadId ?? undefined) },
    { id: "pred", icono: <FileSpreadsheet size={15} />, titulo: "Predicciones (CSV)", detalle: "Próximas 4 semanas, todos los municipios",
      fn: () => reporteApi.prediccionesCsv() },
    { id: "alertas", icono: <FileSpreadsheet size={15} />, titulo: "Alertas (CSV)", detalle: "Historial completo",
      fn: () => reporteApi.alertasCsv() },
  ];

  return (
    <div className="relative" ref={caja}>
      <button onClick={() => setAbierto((v) => !v)} aria-expanded={abierto} aria-haspopup="menu"
        className="inline-flex h-[38px] items-center gap-2 rounded-lg border border-line bg-surface px-3 text-sm font-medium text-ink hover:bg-surface-2">
        <Download size={15} /> Descargar
      </button>
      {abierto && (
        <div role="menu" className="absolute right-0 z-50 mt-1.5 w-72 rounded-xl border border-line bg-surface p-1.5 shadow-xl">
          {opciones.map((o) => (
            <button key={o.id} role="menuitem" onClick={() => bajar(o.id, o.fn)} disabled={cargando != null}
              className="flex w-full items-start gap-2.5 rounded-lg px-2.5 py-2 text-left hover:bg-surface-2 disabled:opacity-60">
              <span className="mt-0.5 text-muted">{cargando === o.id ? <LoaderCircle size={15} className="animate-spin" /> : o.icono}</span>
              <span>
                <span className="block text-sm font-medium text-ink">{o.titulo}</span>
                <span className="block text-[11px] text-muted">{o.detalle}</span>
              </span>
            </button>
          ))}
          {error && <p className="px-2.5 pb-1 pt-1 text-xs text-[var(--st-rojo-ink)]">{error}</p>}
        </div>
      )}
    </div>
  );
}
