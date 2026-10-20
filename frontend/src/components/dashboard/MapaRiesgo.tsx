import "leaflet/dist/leaflet.css";
import L from "leaflet";
import { useMemo } from "react";
import { Circle, CircleMarker, MapContainer, Marker, Popup, TileLayer, Tooltip } from "react-leaflet";
import type { Nivel, RiesgoMunicipio } from "../../api/tipos";
import { useTema } from "../../context/ThemeContext";
import { NIVELES } from "../../lib/formato";

// Cráter del Volcán Galeras (Servicio Geológico Colombiano)
const GALERAS: [number, number] = [1.2208, -77.3592];
const ORDEN: Nivel[] = ["VERDE", "AMARILLO", "NARANJA", "ROJO"];

const iconoVolcan = L.divIcon({
  className: "",
  html: `<svg width="28" height="24" viewBox="0 0 28 24" aria-hidden="true">
    <path d="M2 22 L11 6 L14 9 L17 5 L26 22 Z" fill="#b8692a" stroke="#fff" stroke-width="1.5" stroke-linejoin="round"/>
    <circle cx="19" cy="3" r="1.6" fill="#a8a29e"/></svg>`,
  iconSize: [28, 24],
  iconAnchor: [14, 22],
});

export type ModoMapa = "actual" | "predicho";

/** Nivel que se pinta para un municipio según el modo y la enfermedad elegida ("" = la peor). */
export function nivelDe(f: RiesgoMunicipio, modo: ModoMapa, codigo: string): Nivel {
  const detalle = modo === "actual" ? f.detalle : f.detalle_predicho;
  if (codigo) return (detalle[codigo] ?? "VERDE") as Nivel;
  if (modo === "predicho") return (f.nivel_max_predicho ?? "VERDE") as Nivel;
  return f.nivel_max;
}

export default function MapaRiesgo({ filas, modo, codigo, enfermedades, seleccionado, onSeleccionar }: {
  filas: RiesgoMunicipio[]; modo: ModoMapa; codigo: string; enfermedades: { codigo: string; nombre: string }[];
  seleccionado: number | null; onSeleccionar: (id: number) => void;
}) {
  const { tema } = useTema();
  const limites = useMemo(() => L.latLngBounds([...filas.map((f) => [f.latitud, f.longitud] as [number, number]), GALERAS]).pad(0.25), [filas]);
  // Los municipios con más riesgo se dibujan encima
  const ordenadas = [...filas].sort((a, b) => ORDEN.indexOf(nivelDe(a, modo, codigo)) - ORDEN.indexOf(nivelDe(b, modo, codigo)));

  return (
    <div className="relative isolate h-80 overflow-hidden rounded-lg border border-line sm:h-[26rem]">
      <MapContainer bounds={limites} scrollWheelZoom={false} className="h-full w-full" style={{ background: "var(--surface-2)" }}
        attributionControl>
        <TileLayer key={tema}
          url={`https://{s}.basemaps.cartocdn.com/${tema === "oscuro" ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png`}
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>' />
        <Circle center={GALERAS} radius={15000} interactive={false}
          pathOptions={{ color: "#b8692a", weight: 1, dashArray: "4 6", fillOpacity: 0.04 }} />
        <Marker position={GALERAS} icon={iconoVolcan}>
          <Tooltip direction="top" offset={[0, -18]}>Volcán Galeras · radio de referencia de 15 km</Tooltip>
        </Marker>
        {ordenadas.map((f) => {
          const n = nivelDe(f, modo, codigo);
          const activo = f.municipio_id === seleccionado;
          return (
            <CircleMarker key={`${f.municipio_id}-${modo}-${codigo}-${tema}`} center={[f.latitud, f.longitud]}
              radius={activo ? 15 : 12}
              pathOptions={{ color: tema === "oscuro" ? "#1a1918" : "#ffffff", weight: activo ? 3 : 2,
                             fillColor: NIVELES[n].color, fillOpacity: 0.92 }}
              eventHandlers={{ click: () => onSeleccionar(f.municipio_id) }}>
              <Tooltip direction="right" offset={[12, 0]} permanent className="mapa-etiqueta">
                {f.municipio}
              </Tooltip>
              <Popup>
                <p className="mb-1 text-sm font-semibold">{f.municipio}</p>
                <table className="text-xs">
                  <thead><tr><th className="pr-3 text-left font-medium">Enfermedad</th><th className="pr-3 text-left font-medium">Actual</th><th className="text-left font-medium">4 semanas</th></tr></thead>
                  <tbody>
                    {enfermedades.map((e) => (
                      <tr key={e.codigo}>
                        <td className="pr-3">{e.nombre}</td>
                        <td className="pr-3">{NIVELES[(f.detalle[e.codigo] ?? "VERDE") as Nivel].etiqueta}</td>
                        <td>{f.detalle_predicho[e.codigo] ? NIVELES[f.detalle_predicho[e.codigo]].etiqueta : "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </Popup>
            </CircleMarker>
          );
        })}
      </MapContainer>
      <ul className="pointer-events-none absolute bottom-2 left-2 z-[1000] flex flex-wrap gap-x-3 gap-y-1 rounded-lg border border-line bg-surface/90 px-2.5 py-1.5 text-[11px] text-ink-2 backdrop-blur"
        aria-label="Leyenda del mapa">
        {ORDEN.map((n) => (
          <li key={n} className="flex items-center gap-1.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: NIVELES[n].color }} />{NIVELES[n].etiqueta}
          </li>
        ))}
      </ul>
    </div>
  );
}
