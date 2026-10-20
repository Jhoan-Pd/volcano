import { CheckCircle2, ClipboardList, History, Pencil, Pill, Save, Trash2 } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { mensajeError } from "../api/cliente";
import { farmaciaApi } from "../api/servicios";
import type { Categoria, Farmacia, MiFarmacia, ReporteSemanal } from "../api/tipos";
import { Aviso, Boton, Card, CardHeader, claseInput, Etiqueta, Modal, SimuladoBadge, Spinner } from "../components/ui";
import { useAuth } from "../context/AuthContext";
import TituloRevelado from "../components/TituloRevelado";
import { CATEGORIAS, fmtFecha, fmtNum } from "../lib/formato";

const MAX_UNIDADES = 100_000;
type Valores = Record<Categoria, string>;

const vacio = (cats: Categoria[]): Valores =>
  Object.fromEntries(cats.map((c) => [c, ""])) as Valores;

/** Valida en el navegador lo mismo que valida la API (la API siempre tiene la última palabra). */
function validar(valores: Valores): Partial<Record<Categoria, string>> {
  const errores: Partial<Record<Categoria, string>> = {};
  for (const [cat, v] of Object.entries(valores) as [Categoria, string][]) {
    if (v.trim() === "") errores[cat] = "Obligatorio (escribe 0 si no hubo ventas)";
    else if (!/^\d+$/.test(v.trim())) errores[cat] = "Solo números enteros";
    else if (Number(v) > MAX_UNIDADES) errores[cat] = `Máximo ${fmtNum(MAX_UNIDADES)}`;
  }
  return errores;
}

export default function FarmaciaPage() {
  const { usuario } = useAuth();
  const esAdmin = usuario?.rol === "ADMIN";
  const [farmacias, setFarmacias] = useState<Farmacia[]>([]);
  const [farmaciaId, setFarmaciaId] = useState<number | undefined>(undefined);
  const [info, setInfo] = useState<MiFarmacia | null>(null);
  const [historial, setHistorial] = useState<ReporteSemanal[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const [semana, setSemana] = useState<string>("");
  const [valores, setValores] = useState<Valores | null>(null);
  const [errores, setErrores] = useState<Partial<Record<Categoria, string>>>({});
  const [guardando, setGuardando] = useState(false);
  const [mensaje, setMensaje] = useState<{ tipo: "ok" | "error"; texto: string } | null>(null);
  const [borrando, setBorrando] = useState<ReporteSemanal | null>(null);

  // El ADMIN elige por qué farmacia reporta
  useEffect(() => {
    if (!esAdmin) return;
    farmaciaApi.farmacias().then((fs) => {
      setFarmacias(fs);
      setFarmaciaId((id) => id ?? fs[0]?.id);
    }).catch((e) => setError(mensajeError(e)));
  }, [esAdmin]);

  const cargar = useCallback(async () => {
    if (esAdmin && farmaciaId == null) return;
    try {
      const [i, h] = await Promise.all([farmaciaApi.miFarmacia(farmaciaId), farmaciaApi.historial(farmaciaId)]);
      setInfo(i); setHistorial(h); setError(null);
      setValores((v) => v ?? vacio(i.categorias));
      setSemana((s) => s || `${i.semanas_reportables.find((x) => !x.reportada)?.anio ?? i.semanas_reportables[0].anio}-${
        i.semanas_reportables.find((x) => !x.reportada)?.semana_epi ?? i.semanas_reportables[0].semana_epi}`);
    } catch (e) {
      setError(mensajeError(e));
    }
  }, [esAdmin, farmaciaId]);

  useEffect(() => { cargar(); }, [cargar]);

  const [anioSel, semanaSel] = semana ? semana.split("-").map(Number) : [0, 0];
  const existente = useMemo(
    () => historial?.find((r) => r.anio === anioSel && r.semana_epi === semanaSel) ?? null,
    [historial, anioSel, semanaSel],
  );

  // Al elegir una semana ya reportada se cargan sus valores para editarlos
  useEffect(() => {
    if (!info) return;
    const base = vacio(info.categorias);
    if (existente) for (const it of existente.items) base[it.categoria] = String(it.unidades);
    setValores(base); setErrores({}); setMensaje(null);
  }, [existente, info]);

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!valores || !info) return;
    const errs = validar(valores);
    setErrores(errs);
    if (Object.keys(errs).length) return;
    const items = info.categorias.map((c) => ({ categoria: c, unidades: Number(valores[c]) }));
    setGuardando(true); setMensaje(null);
    try {
      if (existente) await farmaciaApi.actualizar(anioSel, semanaSel, items, farmaciaId);
      else await farmaciaApi.crear({ anio: anioSel, semana_epi: semanaSel, items }, farmaciaId);
      setMensaje({ tipo: "ok", texto: existente ? "Reporte actualizado." : "Reporte registrado. ¡Gracias por reportar!" });
      await cargar();
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeError(err) });
    } finally {
      setGuardando(false);
    }
  }

  async function confirmarBorrado() {
    if (!borrando) return;
    try {
      await farmaciaApi.eliminar(borrando.anio, borrando.semana_epi, farmaciaId);
      setBorrando(null);
      await cargar();
    } catch (err) {
      setMensaje({ tipo: "error", texto: mensajeError(err) });
      setBorrando(null);
    }
  }

  function editar(r: ReporteSemanal) {
    setSemana(`${r.anio}-${r.semana_epi}`);
    document.getElementById("form-reporte")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const grafica = useMemo(
    () => [...(historial ?? [])].reverse().map((r) => ({ etiqueta: r.etiqueta.replace("-S", " · S"), total: r.total_unidades })),
    [historial],
  );

  if (error && !info) return <Aviso tipo="error">{error}</Aviso>;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
        <div>
          <p className="titulo-seccion text-[13px] text-muted">Panel de farmacia</p>
          <TituloRevelado className="titulo-display mt-2 text-[2.6rem] sm:text-6xl" texto={info?.nombre ?? "Cargando…"} />
          {info && <p className="mt-1 text-sm text-ink-2">{info.municipio} · NIT {info.nit}{info.direccion ? ` · ${info.direccion}` : ""}</p>}
        </div>
        {esAdmin && (
          <label className="w-full md:w-72">
            <span className="mb-1 block text-xs font-medium text-ink-2">Reportar como (solo ADMIN)</span>
            <select className={claseInput} value={farmaciaId ?? ""} onChange={(e) => {
              setFarmaciaId(Number(e.target.value)); setSemana(""); setValores(null); setInfo(null); setHistorial(null);
            }}>
              {farmacias.map((f) => <option key={f.id} value={f.id}>{f.nombre}</option>)}
            </select>
          </label>
        )}
      </div>

      {!info ? <Spinner /> : (
        <div className="grid gap-6 lg:grid-cols-5">
          <Card className="min-w-0 lg:col-span-3">
            <div id="form-reporte" className="scroll-mt-20" />
            <CardHeader titulo={existente ? "Editar reporte semanal" : "Nuevo reporte semanal"} icono={<ClipboardList size={17} />}
              subtitulo="Unidades vendidas en la semana epidemiológica (domingo a sábado). Puedes registrar o corregir las últimas 8 semanas." />
            <form onSubmit={guardar} className="space-y-4 px-5 pb-5" noValidate>
              <Etiqueta texto="Semana epidemiológica">
                <select className={claseInput} value={semana} onChange={(e) => setSemana(e.target.value)}>
                  {info.semanas_reportables.map((s) => (
                    <option key={s.etiqueta} value={`${s.anio}-${s.semana_epi}`}>
                      {s.etiqueta.replace("-S", " · semana ")} ({fmtFecha(s.fecha_inicio, { day: "numeric", month: "short" })} – {fmtFecha(s.fecha_fin, { day: "numeric", month: "short" })}){s.reportada ? " ✓ reportada" : ""}
                    </option>
                  ))}
                </select>
              </Etiqueta>
              {existente && (
                <Aviso>Esta semana ya fue reportada{existente.reportado_por ? ` por ${existente.reportado_por}` : ""}. Al guardar se reemplazan los valores.</Aviso>
              )}
              <div className="grid gap-3 sm:grid-cols-2">
                {valores && info.categorias.map((c) => (
                  <Etiqueta key={c} texto={CATEGORIAS[c]?.etiqueta ?? c} ayuda={errores[c] ?? CATEGORIAS[c]?.ayuda}>
                    <input inputMode="numeric" className={`${claseInput} tabular ${errores[c] ? "border-[var(--st-rojo)]" : ""}`}
                      aria-invalid={Boolean(errores[c])} value={valores[c]} placeholder="0"
                      onChange={(e) => setValores({ ...valores, [c]: e.target.value.replace(/[^\d]/g, "") })} />
                  </Etiqueta>
                ))}
              </div>
              {mensaje && <Aviso tipo={mensaje.tipo}>{mensaje.texto}</Aviso>}
              <div className="flex flex-wrap items-center gap-3">
                <Boton type="submit" cargando={guardando} disabled={!info.activa}>
                  <Save size={15} /> {existente ? "Guardar cambios" : "Registrar reporte"}
                </Boton>
                {!info.activa && <span className="text-xs text-muted">La farmacia está inactiva.</span>}
              </div>
            </form>
          </Card>

          <Card className="min-w-0 lg:col-span-2">
            <CardHeader titulo="Unidades por semana" icono={<Pill size={17} />} subtitulo="Total de todas las categorías (últimas 26 semanas)" />
            <div className="h-64 px-3 pb-4">
              {grafica.length === 0 ? <p className="py-10 text-center text-sm text-muted">Aún no hay reportes.</p> : (
                <ResponsiveContainer>
                  <BarChart data={grafica} margin={{ top: 8, right: 8, left: -12, bottom: 0 }}>
                    <CartesianGrid stroke="var(--line)" vertical={false} />
                    <XAxis dataKey="etiqueta" tickLine={false} axisLine={{ stroke: "var(--axis)" }} minTickGap={24} />
                    <YAxis tickLine={false} axisLine={false} width={44} allowDecimals={false} />
                    <Tooltip cursor={{ fill: "var(--surface-2)" }} formatter={(v) => [fmtNum(Number(v)), "Unidades"]}
                      contentStyle={{ background: "var(--surface)", border: "1px solid var(--line)", borderRadius: 12, fontSize: 12 }} />
                    <Bar dataKey="total" fill="var(--series-1)" radius={[4, 4, 0, 0]} maxBarSize={18} isAnimationActive={false} />
                  </BarChart>
                </ResponsiveContainer>
              )}
            </div>
          </Card>
        </div>
      )}

      <Card>
        <CardHeader titulo="Historial de reportes" icono={<History size={17} />} subtitulo="Las semanas antiguas solo las puede corregir el administrador." />
        {historial == null ? <Spinner /> : historial.length === 0 ? (
          <p className="px-5 pb-6 text-sm text-muted">Sin reportes todavía.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="px-5 py-2 font-medium">Semana</th>
                  {info?.categorias.map((c) => <th key={c} className="px-2 py-2 text-right font-medium">{CATEGORIAS[c]?.etiqueta ?? c}</th>)}
                  <th className="px-2 py-2 text-right font-medium">Total</th>
                  <th className="px-2 py-2 font-medium">Origen</th>
                  <th className="px-5 py-2" />
                </tr>
              </thead>
              <tbody>
                {historial.map((r) => {
                  const por = Object.fromEntries(r.items.map((i) => [i.categoria, i.unidades]));
                  return (
                    <tr key={r.etiqueta} className="border-b border-line/70 last:border-0">
                      <td className="px-5 py-2.5">
                        <p className="font-medium tabular">{r.etiqueta.replace("-S", " · S")}</p>
                        <p className="text-[11px] text-muted">{fmtFecha(r.fecha_inicio, { day: "numeric", month: "short" })}</p>
                      </td>
                      {info?.categorias.map((c) => <td key={c} className="px-2 py-2.5 text-right tabular">{fmtNum(por[c])}</td>)}
                      <td className="px-2 py-2.5 text-right font-semibold tabular">{fmtNum(r.total_unidades)}</td>
                      <td className="px-2 py-2.5 text-xs">
                        {r.es_simulado ? <SimuladoBadge /> : (
                          <span className="inline-flex items-center gap-1 text-ink-2"><CheckCircle2 size={13} className="text-[var(--st-verde)]" />{r.reportado_por ?? "Reportado"}</span>
                        )}
                      </td>
                      <td className="px-5 py-2.5 text-right">
                        {r.editable && (
                          <div className="flex justify-end gap-1">
                            <button onClick={() => editar(r)} className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2" aria-label={`Editar ${r.etiqueta}`} title="Editar"><Pencil size={15} /></button>
                            <button onClick={() => setBorrando(r)} className="rounded-md p-1.5 text-[var(--st-rojo-ink)] hover:bg-surface-2" aria-label={`Eliminar ${r.etiqueta}`} title="Eliminar"><Trash2 size={15} /></button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Modal abierto={borrando != null} titulo="Eliminar reporte" onCerrar={() => setBorrando(null)}>
        <p className="text-sm text-ink-2">¿Seguro que quieres eliminar el reporte de la semana <b>{borrando?.etiqueta.replace("-S", " · S")}</b>? Esta acción no se puede deshacer.</p>
        <div className="mt-4 flex justify-end gap-2">
          <Boton variante="secundario" onClick={() => setBorrando(null)}>Cancelar</Boton>
          <Boton variante="peligro" onClick={confirmarBorrado}><Trash2 size={15} /> Eliminar</Boton>
        </div>
      </Modal>
    </div>
  );
}
