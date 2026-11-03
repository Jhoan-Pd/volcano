"use client";

import { Send, UploadCloud } from "lucide-react";
import { useState } from "react";
import { mensajeError } from "@/api/cliente";
import { motorApi } from "@/api/servicios";
import type { FilaCargaFarmacia, ResumenCargaFarmacia } from "@/api/tipos";
import { fmtNum } from "@/lib/formato";
import RevisionCsv from "../RevisionCsv";
import { Aviso, Boton, Card, CardHeader } from "../ui";

/**
 * Carga masiva del histórico de una farmacia.
 * 1. Web Worker: el CSV se lee y valida en otro hilo (categorías, semanas, unidades).
 * 2. Client streaming de gRPC: la API reenvía las filas válidas al motor como un stream; el
 *    motor valida cada una al llegar, agrupa por semana y responde UN resumen al final.
 * Una FARMACIA solo puede cargar las últimas 8 semanas de su propia farmacia (lo verifica el motor).
 */
export default function CargaMasiva({ farmaciaId, alTerminar }: { farmaciaId?: number; alTerminar: () => void }) {
  const [enviando, setEnviando] = useState(false);
  const [resumen, setResumen] = useState<ResumenCargaFarmacia | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function enviar(filas: FilaCargaFarmacia[]) {
    setEnviando(true); setResumen(null); setError(null);
    try {
      setResumen(await motorApi.cargarReportes(filas));
      alTerminar();
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Card>
      <CardHeader titulo="Carga masiva desde CSV" icono={<UploadCloud size={17} />}
        subtitulo="El archivo se revisa en tu navegador (Web Worker) y las filas válidas viajan al motor de predicción como un stream de gRPC." />
      <div className="space-y-3 px-5 pb-5">
        <RevisionCsv tipo="farmacia" accion={(r) => {
          const filas: FilaCargaFarmacia[] = r.normalizadas.map((n) => ({
            fila: Number(n.fila), anio: Number(n.anio), semana_epi: Number(n.semana_epi), categoria: String(n.categoria),
            unidades: Number(n.unidades), farmacia_id: n.farmacia_id == null ? farmaciaId ?? null : Number(n.farmacia_id),
          }));
          return (
            <div className="border-t border-line pt-3">
              <Boton onClick={() => enviar(filas)} cargando={enviando} disabled={filas.length === 0}>
                <Send size={15} /> Enviar {fmtNum(filas.length)} filas por streaming
              </Boton>
            </div>
          );
        }} />
        {error && <Aviso tipo="error">{error}</Aviso>}
        {resumen && (
          <Aviso tipo={resumen.semanas_rechazadas || resumen.filas_rechazadas ? "info" : "ok"}>
            <p>
              El motor recibió {fmtNum(resumen.filas_recibidas)} filas en {fmtNum(resumen.duracion_ms, 0)} ms:{" "}
              {fmtNum(resumen.semanas_creadas)} semanas nuevas, {fmtNum(resumen.semanas_actualizadas)} reemplazadas y{" "}
              {fmtNum(resumen.semanas_rechazadas)} rechazadas{resumen.filas_rechazadas ? ` (${fmtNum(resumen.filas_rechazadas)} filas inválidas)` : ""}.
            </p>
            {resumen.errores.length > 0 && (
              <ul className="mt-2 max-h-40 list-disc space-y-0.5 overflow-y-auto pl-5 text-xs">
                {resumen.errores.map((e, i) => <li key={`${e.fila}-${i}`}>Fila {e.fila}: {e.mensaje}</li>)}
              </ul>
            )}
          </Aviso>
        )}
      </div>
    </Card>
  );
}
