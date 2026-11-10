"use client";

import { Radio, WifiOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { type ReactNode, useEffect, useState } from "react";
import { catalogoApi, dashboardApi } from "../api/servicios";
import MapaRiesgo from "../components/dashboard/MapaDinamico";
import type { ModoMapa } from "../components/dashboard/modoMapa";
import { RiesgoMunicipiosTabla } from "../components/dashboard/Paneles";
import { RenderPanel } from "../components/render/RenderPanel";
import { Aviso, Card, CardHeader, NivelChip, Segmentado, Spinner } from "../components/ui";
import { useAlertasEnVivo, type ModoConexion } from "../lib/useAlertasEnVivo";
import { useDatos } from "../lib/useDatos";

const MODOS = [
  { valor: "actual", etiqueta: "Semana actual" },
  { valor: "predicho", etiqueta: "Próximas 4 semanas" },
] as const satisfies readonly { valor: ModoMapa; etiqueta: string }[];

const CONEXION: Record<ModoConexion, string> = {
  conectando: "Conectando con el motor…",
  "en-vivo": "En vivo · SSE ← gRPC SeguirAlertas",
  reconectando: "Reconectando…",
  "consulta-periodica": "Motor no disponible: consulta cada 5 min",
};

const TIPO: Record<string, string> = { NUEVA: "Nueva", ACTUALIZADA: "Actualizada", CERRADA: "Cerrada", ACTIVA: "Activa" };

/**
 * Mapa de riesgo 100 % en el navegador (CSR): Leaflet, datos por fetch y alertas por SSE.
 * Cuando el stream avisa un cambio en las alertas se vuelve a pedir el riesgo por municipio.
 */
export default function MapaEnVivo({ encabezado }: { encabezado?: ReactNode }) {
  const router = useRouter();
  const [modo, setModo] = useState<ModoMapa>("actual");
  const [codigo, setCodigo] = useState("");
  const { alertas, modo: conexion, cambios, actualizadoEn } = useAlertasEnVivo();
  const riesgo = useDatos(() => dashboardApi.riesgoMunicipios(), []);
  const enfermedades = useDatos(() => catalogoApi.enfermedades(), []);
  const [recibidoEn, setRecibidoEn] = useState<string | null>(null);

  useEffect(() => { if (riesgo.datos) setRecibidoEn(new Date().toISOString()); }, [riesgo.datos]);
  const ultimoCambio = cambios[0]?.momento;
  const { recargar } = riesgo;
  useEffect(() => { if (ultimoCambio) recargar(); }, [ultimoCambio, recargar]);

  const lista = (enfermedades.datos ?? []).filter((e) => e.activo).map((e) => ({ codigo: e.codigo, nombre: e.nombre }));
  const irA = (id: number) => router.push(`/municipio/${id}`);

  return (
    <div className="space-y-5">
      <RenderPanel patron="CSR" generadoEn={recibidoEn}
        detalles={[
          { etiqueta: "Alertas", valor: CONEXION[conexion] },
          { etiqueta: "Último evento del stream", valor: actualizadoEn ? new Date(actualizadoEn).toLocaleTimeString("es-CO") : "—" },
        ]} />
      {encabezado}

      {riesgo.error && <Aviso tipo="error">{riesgo.error}</Aviso>}

      <div className="grid gap-6 lg:grid-cols-3">
        <Card className="min-w-0 lg:col-span-2">
          <CardHeader titulo="Mapa de riesgo" subtitulo="Haz clic en un municipio para abrir su tablero."
            accion={
              <div className="flex flex-wrap items-center gap-2">
                <select className="rounded-lg border border-line bg-surface px-2 py-1.5 text-xs text-ink focus:border-accent focus:outline-none"
                  value={codigo} onChange={(e) => setCodigo(e.target.value)} aria-label="Enfermedad del mapa">
                  <option value="">Todas (la de mayor riesgo)</option>
                  {lista.map((e) => <option key={e.codigo} value={e.codigo}>{e.nombre}</option>)}
                </select>
                <Segmentado etiqueta="Periodo del mapa" opciones={MODOS} valor={modo} onCambiar={setModo} />
              </div>
            } />
          <div className="px-5 pb-5">
            {!riesgo.datos ? <Spinner texto="Pidiendo el riesgo por municipio…" /> : (
              <MapaRiesgo filas={riesgo.datos} modo={modo} codigo={codigo} seleccionado={null} enfermedades={lista} onSeleccionar={irA} />
            )}
          </div>
        </Card>

        <div className="min-w-0 space-y-6">
          <Card>
            <CardHeader titulo={`Alertas activas (${alertas.length})`}
              accion={
                <span className="inline-flex items-center gap-1.5 text-[11px] text-muted" role="status">
                  {conexion === "en-vivo"
                    ? <><Radio size={13} className="animate-pulse text-[var(--st-verde)]" aria-hidden /> en vivo</>
                    : <><WifiOff size={13} aria-hidden /> {conexion === "conectando" ? "conectando" : "sin stream"}</>}
                </span>
              } />
            <ul className="max-h-80 space-y-2 overflow-y-auto px-5 pb-5">
              {alertas.length === 0 && <li className="text-sm text-muted">Sin alertas activas.</li>}
              {alertas.map((a) => (
                <li key={a.id} className="rounded-lg border border-line p-2.5 text-xs">
                  <div className="flex items-center gap-2"><NivelChip nivel={a.nivel} /><b className="font-medium">{a.municipio}</b>
                    <span className="text-muted">{a.enfermedad}</span></div>
                  <p className="mt-1 text-ink-2">{a.mensaje}</p>
                </li>
              ))}
            </ul>
          </Card>
          <Card>
            <CardHeader titulo="Cambios recibidos" subtitulo="Eventos que el motor empujó desde que abriste la página" />
            <ul className="space-y-1.5 px-5 pb-5 text-xs">
              {cambios.length === 0 && <li className="text-muted">Todavía ninguno. Cuando el cron o un reentrenamiento cambien una alerta aparecerá aquí sin recargar.</li>}
              {cambios.map((c, i) => (
                <li key={`${c.momento}-${i}`} className="entrar flex items-center gap-2">
                  <span className="tabular text-muted">{new Date(c.momento).toLocaleTimeString("es-CO")}</span>
                  <b className="font-medium">{TIPO[c.tipo]}</b> {c.alerta.municipio} · {c.alerta.enfermedad}
                </li>
              ))}
            </ul>
          </Card>
        </div>
      </div>

      {riesgo.datos && (
        <Card className="min-w-0">
          <CardHeader titulo="Riesgo por municipio" />
          <RiesgoMunicipiosTabla filas={riesgo.datos} enfermedades={lista} seleccionado={null}
            predicho={modo === "predicho"} onSeleccionar={irA} />
        </Card>
      )}
    </div>
  );
}
