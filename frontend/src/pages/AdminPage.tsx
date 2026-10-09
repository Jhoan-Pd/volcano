import { BrainCircuit, Bug, Database, MapPin, Mountain, Pill, Users } from "lucide-react";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { catalogoApi } from "../api/servicios";
import type { Municipio } from "../api/tipos";
import CrudTable, { type Campo } from "../components/admin/CrudTable";
import PanelDatos from "../components/admin/PanelDatos";
import PanelModelo from "../components/admin/PanelModelo";
import { Card } from "../components/ui";

const NIVELES = ["VERDE", "AMARILLO", "NARANJA", "ROJO"].map((n) => ({ valor: n, etiqueta: n.charAt(0) + n.slice(1).toLowerCase() }));
const TIPOS_EVENTO = [
  { valor: "BOLETIN", etiqueta: "Boletín SGC" }, { valor: "CAIDA_CENIZA", etiqueta: "Caída de ceniza" },
  { valor: "EMISION_GASES", etiqueta: "Emisión de gases" }, { valor: "SISMO", etiqueta: "Sismo" },
];

type Pestana = "enfermedades" | "municipios" | "farmacias" | "usuarios" | "eventos" | "datos" | "modelo";

export default function AdminPage() {
  const [pestana, setPestana] = useState<Pestana>("enfermedades");
  const [municipios, setMunicipios] = useState<Municipio[]>([]);

  useEffect(() => { catalogoApi.municipios().then(setMunicipios).catch(() => undefined); }, []);
  const opcMunicipios = useMemo(() => municipios.map((m) => ({ valor: m.id, etiqueta: m.nombre })), [municipios]);

  const campos: Record<Exclude<Pestana, "datos" | "modelo">, { titulo: string; recurso: string; campos: Campo[]; descripcion?: string }> = {
    enfermedades: {
      titulo: "Enfermedades", recurso: "enfermedades",
      descripcion: "Los umbrales son los percentiles del canal endémico que definen el semáforo.",
      campos: [
        { nombre: "codigo", etiqueta: "Código", tipo: "texto", requerido: true, ayuda: "Mayúsculas, ej. IRA" },
        { nombre: "nombre", etiqueta: "Nombre", tipo: "texto", requerido: true },
        { nombre: "codigo_cie10", etiqueta: "CIE-10", tipo: "texto" },
        { nombre: "color", etiqueta: "Color", tipo: "color", defecto: "#2a78d6" },
        { nombre: "umbral_amarillo_pct", etiqueta: "P. amarillo", tipo: "numero", defecto: 50 },
        { nombre: "umbral_naranja_pct", etiqueta: "P. naranja", tipo: "numero", defecto: 75 },
        { nombre: "umbral_rojo_pct", etiqueta: "P. rojo", tipo: "numero", defecto: 90 },
        { nombre: "terminos_busqueda", etiqueta: "Términos de búsqueda", tipo: "texto", enTabla: false, ayuda: "Separados por coma (Google Trends)", ancho: "completo" },
        { nombre: "codigos_sivigila", etiqueta: "Códigos SIVIGILA", tipo: "texto", enTabla: false, ayuda: "Eventos INS separados por coma, ej. 210,220" },
        { nombre: "categorias_farmacia", etiqueta: "Categorías de farmacia", tipo: "texto", enTabla: false, ayuda: "Ej. ANTIGRIPALES,ANTIPIRETICOS" },
        { nombre: "descripcion", etiqueta: "Descripción", tipo: "textarea" },
        { nombre: "recomendaciones", etiqueta: "Recomendaciones (una por línea)", tipo: "textarea" },
        { nombre: "activo", etiqueta: "Activa", tipo: "booleano" },
      ],
    },
    municipios: {
      titulo: "Municipios", recurso: "municipios",
      campos: [
        { nombre: "codigo_divipola", etiqueta: "DIVIPOLA", tipo: "texto", requerido: true, ayuda: "5 dígitos" },
        { nombre: "nombre", etiqueta: "Nombre", tipo: "texto", requerido: true },
        { nombre: "departamento", etiqueta: "Departamento", tipo: "texto", defecto: "Nariño", enTabla: false },
        { nombre: "latitud", etiqueta: "Latitud", tipo: "numero", requerido: true, paso: "any" },
        { nombre: "longitud", etiqueta: "Longitud", tipo: "numero", requerido: true, paso: "any" },
        { nombre: "altitud_m", etiqueta: "Altitud (m)", tipo: "numero" },
        { nombre: "poblacion", etiqueta: "Población", tipo: "numero", requerido: true },
        { nombre: "distancia_crater_km", etiqueta: "Dist. cráter (km)", tipo: "numero", paso: "any" },
        { nombre: "activo", etiqueta: "Activo", tipo: "booleano" },
      ],
    },
    farmacias: {
      titulo: "Farmacias", recurso: "farmacias",
      descripcion: "Farmacias de demostración (ficticias). El usuario asignado debe tener rol FARMACIA.",
      campos: [
        { nombre: "nombre", etiqueta: "Nombre", tipo: "texto", requerido: true },
        { nombre: "nit", etiqueta: "NIT", tipo: "texto", requerido: true, ayuda: "Ej. 900123456-7" },
        { nombre: "municipio_id", etiqueta: "Municipio", tipo: "select", requerido: true, opciones: opcMunicipios },
        { nombre: "direccion", etiqueta: "Dirección", tipo: "texto" },
        { nombre: "telefono", etiqueta: "Teléfono", tipo: "texto" },
        { nombre: "usuario_id", etiqueta: "ID usuario", tipo: "numero", ayuda: "Usuario con rol FARMACIA (opcional)" },
        { nombre: "latitud", etiqueta: "Latitud", tipo: "numero", paso: "any", enTabla: false },
        { nombre: "longitud", etiqueta: "Longitud", tipo: "numero", paso: "any", enTabla: false },
        { nombre: "activa", etiqueta: "Activa", tipo: "booleano" },
      ],
    },
    usuarios: {
      titulo: "Usuarios", recurso: "usuarios",
      campos: [
        { nombre: "nombre", etiqueta: "Nombre", tipo: "texto", requerido: true },
        { nombre: "email", etiqueta: "Correo", tipo: "email", requerido: true },
        { nombre: "rol", etiqueta: "Rol", tipo: "select", requerido: true, defecto: "CIUDADANO",
          opciones: [{ valor: "ADMIN", etiqueta: "ADMIN" }, { valor: "FARMACIA", etiqueta: "FARMACIA" }, { valor: "CIUDADANO", etiqueta: "CIUDADANO" }] },
        { nombre: "municipio_id", etiqueta: "Municipio", tipo: "select", opciones: opcMunicipios },
        { nombre: "password", etiqueta: "Contraseña", tipo: "password", requerido: true, ayuda: "Mín. 8 caracteres con letras y números" },
        { nombre: "activo", etiqueta: "Activo", tipo: "booleano" },
      ],
    },
    eventos: {
      titulo: "Eventos volcánicos", recurso: "eventos-volcanicos",
      descripcion: "Registra el nivel de cada boletín del Servicio Geológico Colombiano y las caídas de ceniza por municipio.",
      campos: [
        { nombre: "tipo", etiqueta: "Tipo", tipo: "select", requerido: true, opciones: TIPOS_EVENTO, defecto: "BOLETIN" },
        { nombre: "nivel_actividad", etiqueta: "Nivel SGC", tipo: "select", requerido: true, opciones: NIVELES, defecto: "AMARILLO" },
        { nombre: "fecha_inicio", etiqueta: "Fecha inicio", tipo: "fecha", requerido: true },
        { nombre: "fecha_fin", etiqueta: "Fecha fin", tipo: "fecha", enTabla: false },
        { nombre: "municipio_id", etiqueta: "Municipio afectado", tipo: "select", opciones: opcMunicipios },
        { nombre: "intensidad_ceniza", etiqueta: "Ceniza (0-3)", tipo: "numero", defecto: 0, ayuda: "0 ninguna · 1 leve · 2 moderada · 3 fuerte" },
        { nombre: "so2_ton_dia", etiqueta: "SO₂ (t/día)", tipo: "numero", paso: "any" },
        { nombre: "url_boletin", etiqueta: "URL del boletín", tipo: "texto", enTabla: false, ancho: "completo" },
        { nombre: "descripcion", etiqueta: "Descripción", tipo: "textarea" },
        { nombre: "es_simulado", etiqueta: "Simulado", tipo: "booleano", enFormulario: false },
      ],
    },
  };

  const pestanas: { id: Pestana; etiqueta: string; icono: ReactNode }[] = [
    { id: "enfermedades", etiqueta: "Enfermedades", icono: <Bug size={15} /> },
    { id: "municipios", etiqueta: "Municipios", icono: <MapPin size={15} /> },
    { id: "farmacias", etiqueta: "Farmacias", icono: <Pill size={15} /> },
    { id: "usuarios", etiqueta: "Usuarios", icono: <Users size={15} /> },
    { id: "eventos", etiqueta: "Eventos volcánicos", icono: <Mountain size={15} /> },
    { id: "datos", etiqueta: "Fuentes de datos", icono: <Database size={15} /> },
    { id: "modelo", etiqueta: "Modelo", icono: <BrainCircuit size={15} /> },
  ];

  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-accent">Panel de administración</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Gestión de datos</h1>
      </div>
      <div className="flex gap-1 overflow-x-auto border-b border-line" role="tablist">
        {pestanas.map((p) => (
          <button key={p.id} role="tab" aria-selected={pestana === p.id} onClick={() => setPestana(p.id)}
            className={`-mb-px inline-flex shrink-0 items-center gap-1.5 border-b-2 px-3 py-2 text-sm font-medium transition ${
              pestana === p.id ? "border-accent text-ink" : "border-transparent text-muted hover:text-ink"}`}>
            {p.icono}{p.etiqueta}
          </button>
        ))}
      </div>
      <Card className="p-5">
        {pestana === "datos" ? <PanelDatos /> : pestana === "modelo" ? <PanelModelo /> : <CrudTable key={pestana} {...campos[pestana]} />}
      </Card>
    </div>
  );
}
