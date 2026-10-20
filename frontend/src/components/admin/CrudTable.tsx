import { ChevronLeft, ChevronRight, Pencil, Plus, Trash2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { mensajeError } from "../../api/cliente";
import { crudApi } from "../../api/servicios";
import { Aviso, Boton, claseInput, Etiqueta, Modal, Spinner } from "../ui";

export type TipoCampo = "texto" | "numero" | "email" | "password" | "booleano" | "select" | "fecha" | "textarea" | "color";

export interface Campo {
  nombre: string;
  etiqueta: string;
  tipo: TipoCampo;
  requerido?: boolean;
  opciones?: { valor: string | number; etiqueta: string }[];
  enTabla?: boolean;
  enFormulario?: boolean;
  soloCrear?: boolean;
  ayuda?: string;
  paso?: string;
  ancho?: "completo";
  formato?: (valor: unknown, fila: Record<string, unknown>) => string;
  defecto?: unknown;
}

type Fila = Record<string, unknown> & { id: number };

const POR_PAGINA = 15;

function valorInicial(c: Campo, fila?: Fila) {
  const v = fila ? fila[c.nombre] : c.defecto;
  if (c.tipo === "booleano") return v ?? true;
  if (c.tipo === "password") return "";
  return v ?? "";
}

/** Normaliza lo escrito en el formulario al tipo que espera la API (números, null, booleanos). */
function normalizar(c: Campo, v: unknown): unknown {
  if (c.tipo === "booleano") return Boolean(v);
  if (v === "" || v === undefined) return null;
  if (c.tipo === "numero") return Number(v);
  if (c.tipo === "select" && c.opciones?.length && typeof c.opciones[0].valor === "number") return Number(v);
  return v;
}

export default function CrudTable({ recurso, titulo, campos, descripcion }: {
  recurso: string; titulo: string; campos: Campo[]; descripcion?: string;
}) {
  const [filas, setFilas] = useState<Fila[]>([]);
  const [total, setTotal] = useState(0);
  const [pagina, setPagina] = useState(0);
  const [cargando, setCargando] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editando, setEditando] = useState<Fila | "nuevo" | null>(null);
  const [borrando, setBorrando] = useState<Fila | null>(null);
  const [form, setForm] = useState<Record<string, unknown>>({});
  const [errorForm, setErrorForm] = useState<string | null>(null);
  const [guardando, setGuardando] = useState(false);

  const cargar = useCallback(async () => {
    setCargando(true); setError(null);
    try {
      const p = await crudApi.listar<Fila>(recurso, pagina * POR_PAGINA, POR_PAGINA);
      setFilas(p.items); setTotal(p.total);
    } catch (e) {
      setError(mensajeError(e));
    } finally {
      setCargando(false);
    }
  }, [recurso, pagina]);

  useEffect(() => { cargar(); }, [cargar]);

  const columnas = campos.filter((c) => c.enTabla !== false && c.tipo !== "password" && c.tipo !== "textarea");
  const camposForm = (esNuevo: boolean) => campos.filter((c) => c.enFormulario !== false && (esNuevo || !c.soloCrear));

  function abrir(fila: Fila | "nuevo") {
    const base = fila === "nuevo" ? undefined : fila;
    setForm(Object.fromEntries(campos.map((c) => [c.nombre, valorInicial(c, base)])));
    setErrorForm(null);
    setEditando(fila);
  }

  async function guardar(e: FormEvent) {
    e.preventDefault();
    if (!editando) return;
    const esNuevo = editando === "nuevo";
    const datos: Record<string, unknown> = {};
    for (const c of camposForm(esNuevo)) {
      const v = normalizar(c, form[c.nombre]);
      if (c.tipo === "password" && !v) continue; // en edición, contraseña vacía = no cambiar
      if (!esNuevo && JSON.stringify(v) === JSON.stringify(normalizar(c, (editando as Fila)[c.nombre]))) continue;
      if (esNuevo && v === null && !c.requerido) continue;
      datos[c.nombre] = v;
    }
    setGuardando(true); setErrorForm(null);
    try {
      if (esNuevo) await crudApi.crear(recurso, datos);
      else if (Object.keys(datos).length) await crudApi.actualizar(recurso, (editando as Fila).id, datos);
      setEditando(null);
      await cargar();
    } catch (err) {
      setErrorForm(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  }

  async function eliminar() {
    if (!borrando) return;
    setGuardando(true);
    try {
      await crudApi.eliminar(recurso, borrando.id);
      setBorrando(null);
      await cargar();
    } catch (err) {
      setBorrando(null);
      setError(mensajeError(err));
    } finally {
      setGuardando(false);
    }
  }

  const mostrar = (c: Campo, fila: Fila) => {
    const v = fila[c.nombre];
    if (c.formato) return c.formato(v, fila);
    if (c.tipo === "booleano") return v ? "Sí" : "No";
    if (c.tipo === "select") return c.opciones?.find((o) => String(o.valor) === String(v))?.etiqueta ?? (v == null ? "—" : String(v));
    if (c.tipo === "color") return String(v ?? "");
    if (v == null || v === "") return "—";
    return typeof v === "number" ? v.toLocaleString("es-CO") : String(v);
  };

  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA));

  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="titulo-seccion text-2xl">{titulo}</h2>
          <p className="text-xs text-muted">{descripcion ?? `${total} registros`}</p>
        </div>
        <Boton onClick={() => abrir("nuevo")}><Plus size={16} /> Nuevo</Boton>
      </div>
      {error && <div className="mb-3"><Aviso tipo="error">{error}</Aviso></div>}
      <div className="overflow-x-auto rounded-xl border border-line">
        <table className="w-full min-w-[640px] text-sm">
          <thead className="bg-surface-2 text-left text-xs text-muted">
            <tr>
              <th className="px-3 py-2.5 font-medium">ID</th>
              {columnas.map((c) => <th key={c.nombre} className="px-3 py-2.5 font-medium">{c.etiqueta}</th>)}
              <th className="px-3 py-2.5 text-right font-medium">Acciones</th>
            </tr>
          </thead>
          <tbody>
            {cargando ? (
              <tr><td colSpan={columnas.length + 2}><Spinner /></td></tr>
            ) : filas.length === 0 ? (
              <tr><td colSpan={columnas.length + 2} className="py-10 text-center text-muted">Sin registros</td></tr>
            ) : filas.map((f) => (
              <tr key={f.id} className="border-t border-line hover:bg-surface-2/60">
                <td className="px-3 py-2 text-muted tabular">{f.id}</td>
                {columnas.map((c) => (
                  <td key={c.nombre} className="max-w-[260px] truncate px-3 py-2" title={mostrar(c, f)}>
                    {c.tipo === "color"
                      ? <span className="inline-flex items-center gap-1.5"><span className="h-3 w-3 rounded" style={{ background: String(f[c.nombre]) }} />{mostrar(c, f)}</span>
                      : mostrar(c, f)}
                  </td>
                ))}
                <td className="whitespace-nowrap px-3 py-2 text-right">
                  <button onClick={() => abrir(f)} className="rounded-md p-1.5 text-ink-2 hover:bg-surface-2" aria-label={`Editar ${f.id}`}><Pencil size={15} /></button>
                  <button onClick={() => setBorrando(f)} className="rounded-md p-1.5 text-[var(--st-rojo-ink)] hover:bg-surface-2" aria-label={`Eliminar ${f.id}`}><Trash2 size={15} /></button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {paginas > 1 && (
        <div className="mt-3 flex items-center justify-end gap-2 text-xs text-ink-2">
          <button disabled={pagina === 0} onClick={() => setPagina(pagina - 1)} className="rounded-md border border-line p-1 disabled:opacity-40" aria-label="Página anterior"><ChevronLeft size={15} /></button>
          <span className="tabular">Página {pagina + 1} de {paginas}</span>
          <button disabled={pagina + 1 >= paginas} onClick={() => setPagina(pagina + 1)} className="rounded-md border border-line p-1 disabled:opacity-40" aria-label="Página siguiente"><ChevronRight size={15} /></button>
        </div>
      )}

      <Modal abierto={editando !== null} titulo={editando === "nuevo" ? `Nuevo registro · ${titulo}` : `Editar #${(editando as Fila | null)?.id ?? ""}`}
        onCerrar={() => setEditando(null)} ancho="max-w-2xl">
        <form onSubmit={guardar} className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            {editando && camposForm(editando === "nuevo").map((c) => (
              <div key={c.nombre} className={c.tipo === "textarea" || c.ancho === "completo" ? "sm:col-span-2" : ""}>
                <Etiqueta texto={`${c.etiqueta}${c.requerido ? " *" : ""}`} ayuda={c.ayuda}>
                  <CampoInput c={c} valor={form[c.nombre]} onChange={(v) => setForm({ ...form, [c.nombre]: v })} esNuevo={editando === "nuevo"} />
                </Etiqueta>
              </div>
            ))}
          </div>
          {errorForm && <Aviso tipo="error">{errorForm}</Aviso>}
          <div className="flex justify-end gap-2 border-t border-line pt-4">
            <Boton type="button" variante="secundario" onClick={() => setEditando(null)}>Cancelar</Boton>
            <Boton type="submit" cargando={guardando}>Guardar</Boton>
          </div>
        </form>
      </Modal>

      <Modal abierto={borrando !== null} titulo="Confirmar eliminación" onCerrar={() => setBorrando(null)}>
        <p className="text-sm">¿Eliminar el registro <b>#{borrando?.id}</b>? Esta acción no se puede deshacer.</p>
        <div className="mt-5 flex justify-end gap-2">
          <Boton variante="secundario" onClick={() => setBorrando(null)}>Cancelar</Boton>
          <Boton variante="peligro" cargando={guardando} onClick={eliminar}><Trash2 size={15} /> Eliminar</Boton>
        </div>
      </Modal>
    </div>
  );
}

function CampoInput({ c, valor, onChange, esNuevo }: { c: Campo; valor: unknown; onChange: (v: unknown) => void; esNuevo: boolean }) {
  const str = valor == null ? "" : String(valor);
  switch (c.tipo) {
    case "booleano":
      return (
        <label className="flex h-[38px] items-center gap-2 text-sm">
          <input type="checkbox" checked={Boolean(valor)} onChange={(e) => onChange(e.target.checked)} className="h-4 w-4 accent-[var(--accent)]" />
          Activo
        </label>
      );
    case "select":
      return (
        <select className={claseInput} value={str} onChange={(e) => onChange(e.target.value)} required={c.requerido}>
          {!c.requerido && <option value="">— Ninguno —</option>}
          {c.requerido && !str && <option value="" disabled>Selecciona…</option>}
          {c.opciones?.map((o) => <option key={o.valor} value={o.valor}>{o.etiqueta}</option>)}
        </select>
      );
    case "textarea":
      return <textarea className={`${claseInput} min-h-[96px]`} value={str} onChange={(e) => onChange(e.target.value)} required={c.requerido} />;
    case "color":
      return (
        <div className="flex gap-2">
          <input type="color" value={str || "#2a78d6"} onChange={(e) => onChange(e.target.value)} className="h-[38px] w-12 rounded border border-line bg-surface" />
          <input className={claseInput} value={str} onChange={(e) => onChange(e.target.value)} pattern="^#[0-9a-fA-F]{6}$" />
        </div>
      );
    default:
      return (
        <input className={claseInput} value={str} onChange={(e) => onChange(e.target.value)}
          type={{ texto: "text", numero: "number", email: "email", password: "password", fecha: "date" }[c.tipo] ?? "text"}
          step={c.paso} required={c.requerido && (c.tipo !== "password" || esNuevo)}
          placeholder={c.tipo === "password" && !esNuevo ? "Déjala vacía para no cambiarla" : undefined}
          autoComplete={c.tipo === "password" ? "new-password" : "off"} />
      );
  }
}
