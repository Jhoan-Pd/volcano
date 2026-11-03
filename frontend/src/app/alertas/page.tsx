// ============================================================================
// BÚSQUEDA DE ALERTAS — SSR (Server-Side Rendering)
// ----------------------------------------------------------------------------
// force-dynamic: se renderiza en el servidor en CADA petición, con los filtros de la URL
// (?q=&municipio=&nivel=…) y las cabeceras de la petición. El formulario es un <form method="get">
// normal: funciona incluso sin JavaScript y cada búsqueda queda en una URL que se puede compartir.
// ============================================================================
import { Search } from "lucide-react";
import type { Metadata } from "next";
import Link from "next/link";
import type { Alerta, Enfermedad, Municipio, Pagina } from "@/api/tipos";
import { RenderPanel } from "@/components/render/RenderPanel";
import { Card, claseInput, NivelChip } from "@/components/ui";
import { fmtFecha } from "@/lib/formato";
import { datosDePeticion, entero, texto, type Busqueda } from "@/lib/peticion";
import { ahoraIso, pedir } from "@/lib/servidor";

export const dynamic = "force-dynamic";
export const maxDuration = 60; // Vercel: dar tiempo a que despierte el backend de Render
export const metadata: Metadata = { title: "Buscar alertas", description: "Historial de alertas tempranas por municipio, enfermedad y nivel." };

const POR_PAGINA = 20;
const ESTADOS = { activas: true, cerradas: false, todas: undefined } as const;

export default async function BuscarAlertas({ searchParams }: { searchParams: Promise<Busqueda> }) {
  const sp = await searchParams;
  const filtros = {
    q: texto(sp.q), municipio: entero(sp.municipio), enfermedad: entero(sp.enfermedad),
    nivel: ["NARANJA", "ROJO"].includes(texto(sp.nivel)) ? texto(sp.nivel) : "",
    origen: ["OBSERVADO", "PREDICHO"].includes(texto(sp.origen)) ? texto(sp.origen) : "",
    estado: (texto(sp.estado) in ESTADOS ? texto(sp.estado) : "activas") as keyof typeof ESTADOS,
    pagina: Math.max(1, entero(sp.pagina) ?? 1),
  };

  const [resultado, municipios, enfermedades, peticion] = await Promise.all([
    pedir<Pagina<Alerta>>("/alertas/buscar", {
      q: filtros.q, municipio_id: filtros.municipio, enfermedad_id: filtros.enfermedad, nivel: filtros.nivel,
      origen: filtros.origen, activa: ESTADOS[filtros.estado], offset: (filtros.pagina - 1) * POR_PAGINA, limit: POR_PAGINA,
    }, { cache: "no-store" }),
    // Los catálogos casi no cambian: aunque la página sea SSR, estos sí se cachean una hora
    pedir<Pagina<Municipio>>("/municipios", { limit: 500 }, { revalidar: 3600 }),
    pedir<Pagina<Enfermedad>>("/enfermedades", { limit: 100 }, { revalidar: 3600 }),
    datosDePeticion(),
  ]);
  const paginas = Math.max(1, Math.ceil(resultado.total / POR_PAGINA));
  const enlace = (pagina: number) => {
    const p = new URLSearchParams(Object.entries({ ...filtros, pagina }).filter(([, v]) => v !== "" && v !== undefined)
      .map(([k, v]) => [k, String(v)]));
    return `/alertas?${p}`;
  };

  return (
    <div className="space-y-5">
      <RenderPanel patron="SSR" generadoEn={ahoraIso()}
        detalles={[
          { etiqueta: "Filtros leídos de la URL", valor: Object.entries(filtros).filter(([k, v]) => v && k !== "pagina").map(([k]) => k).join(", ") || "ninguno" },
          { etiqueta: "Renderizado para", valor: `${peticion.navegador} · ${peticion.idioma} · ${peticion.region}` },
        ]} />

      <header>
        <p className="titulo-seccion text-[13px] text-muted">Historial</p>
        <h1 className="titulo-display mt-2 text-5xl sm:text-6xl">Buscar alertas</h1>
      </header>

      <Card>
        <form method="get" action="/alertas" className="grid gap-3 p-4 sm:grid-cols-2 lg:grid-cols-6" role="search">
          <label className="lg:col-span-2">
            <span className="mb-1 block text-xs font-medium text-ink-2">Texto</span>
            <input name="q" defaultValue={filtros.q} placeholder="dengue, Consacá, ceniza…" className={claseInput} />
          </label>
          <Selector nombre="municipio" etiqueta="Municipio" valor={filtros.municipio}
            opciones={municipios.items.map((m) => [String(m.id), m.nombre])} />
          <Selector nombre="enfermedad" etiqueta="Enfermedad" valor={filtros.enfermedad}
            opciones={enfermedades.items.map((e) => [String(e.id), e.nombre])} />
          <Selector nombre="nivel" etiqueta="Nivel" valor={filtros.nivel} opciones={[["NARANJA", "Alto"], ["ROJO", "Muy alto"]]} />
          <Selector nombre="estado" etiqueta="Estado" valor={filtros.estado} sinTodos
            opciones={[["activas", "Activas"], ["cerradas", "Cerradas"], ["todas", "Todas"]]} />
          <Selector nombre="origen" etiqueta="Origen" valor={filtros.origen} opciones={[["OBSERVADO", "Observado"], ["PREDICHO", "Predicho"]]} />
          <div className="flex items-end gap-2 lg:col-span-5">
            <button className="inline-flex items-center gap-2 rounded-lg bg-ink px-3.5 py-2 text-sm font-medium text-page hover:opacity-90">
              <Search size={15} aria-hidden /> Buscar
            </button>
            <Link href="/alertas" className="rounded-lg px-3 py-2 text-sm text-ink-2 hover:bg-surface-2">Limpiar</Link>
          </div>
        </form>
      </Card>

      <p className="text-sm text-ink-2">{resultado.total} alerta{resultado.total === 1 ? "" : "s"} · página {filtros.pagina} de {paginas}</p>

      {resultado.items.length === 0 ? (
        <Card><p className="py-10 text-center text-sm text-muted">No hay alertas con esos filtros.</p></Card>
      ) : (
        <ul className="space-y-2">
          {resultado.items.map((a) => (
            <li key={a.id} data-alerta={a.id} className="rounded-lg border border-line bg-surface p-4">
              <div className="flex flex-wrap items-center gap-2">
                <NivelChip nivel={a.nivel_riesgo} />
                <span className="rounded-full border border-line px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-muted">
                  {a.origen === "OBSERVADO" ? "Observado" : "Predicho"}</span>
                <Link href={`/municipio/${a.municipio_id}`} className="subrayar text-sm font-medium">{a.municipio}</Link>
                <span className="text-sm text-ink-2">· {a.enfermedad} · semana {a.etiqueta}</span>
                <span className="ml-auto text-xs text-muted">{a.activa ? "Activa" : `Cerrada ${fmtFecha(a.cerrada_en)}`}</span>
              </div>
              <p className="mt-2 text-sm text-ink-2">{a.mensaje}</p>
            </li>
          ))}
        </ul>
      )}

      {paginas > 1 && (
        <nav className="flex items-center justify-center gap-2 text-sm" aria-label="Paginación">
          {filtros.pagina > 1 && <Link href={enlace(filtros.pagina - 1)} className="rounded-lg border border-line px-3 py-1.5 hover:bg-surface-2">← Anterior</Link>}
          {filtros.pagina < paginas && <Link href={enlace(filtros.pagina + 1)} className="rounded-lg border border-line px-3 py-1.5 hover:bg-surface-2">Siguiente →</Link>}
        </nav>
      )}
    </div>
  );
}

function Selector({ nombre, etiqueta, valor, opciones, sinTodos = false }: {
  nombre: string; etiqueta: string; valor: string | number | undefined; opciones: string[][]; sinTodos?: boolean;
}) {
  return (
    <label>
      <span className="mb-1 block text-xs font-medium text-ink-2">{etiqueta}</span>
      <select name={nombre} defaultValue={valor === undefined ? "" : String(valor)} className={claseInput}>
        {!sinTodos && <option value="">Todos</option>}
        {opciones.map(([v, t]) => <option key={v} value={v}>{t}</option>)}
      </select>
    </label>
  );
}
