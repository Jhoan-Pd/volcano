import { ClipboardList, Pill } from "lucide-react";
import { Card, CardHeader } from "../components/ui";
import { useAuth } from "../context/AuthContext";

const CATEGORIAS = ["Antigripales", "Antipiréticos", "Sales de rehidratación", "Inhaladores", "Tapabocas", "Repelentes"];

/** Panel de farmacia: el formulario de reporte semanal se implementa en la Fase 2. */
export default function FarmaciaPage() {
  const { usuario } = useAuth();
  return (
    <div className="space-y-6">
      <div>
        <p className="text-xs font-medium uppercase tracking-wider text-accent">Panel de farmacia</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">Hola, {usuario?.nombre}</h1>
      </div>
      <Card>
        <CardHeader titulo="Reporte semanal de ventas" icono={<ClipboardList size={17} />}
          subtitulo="Disponible en la Fase 2: formulario con validaciones, historial y edición de reportes." />
        <div className="px-5 pb-5">
          <p className="text-sm text-ink-2">Cada semana epidemiológica reportarás las unidades vendidas por categoría:</p>
          <ul className="mt-3 grid gap-2 sm:grid-cols-3">
            {CATEGORIAS.map((c) => (
              <li key={c} className="flex items-center gap-2 rounded-xl bg-surface-2 px-3 py-2 text-sm">
                <Pill size={14} className="text-muted" aria-hidden />{c}
              </li>
            ))}
          </ul>
          <p className="mt-4 text-xs text-muted">Las ventas de estos productos suelen subir días antes de que aumenten las consultas médicas, por eso son una señal temprana del modelo.</p>
        </div>
      </Card>
    </div>
  );
}
