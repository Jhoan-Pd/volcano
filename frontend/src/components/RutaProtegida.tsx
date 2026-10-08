import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import type { Rol } from "../api/tipos";
import { useAuth } from "../context/AuthContext";
import { Aviso, Spinner } from "./ui";

/** Protege rutas por rol. El backend valida de nuevo: esto solo mejora la experiencia. */
export default function RutaProtegida({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { usuario, cargando, tieneRol } = useAuth();
  const location = useLocation();
  if (cargando) return <Spinner texto="Verificando sesión…" />;
  if (!usuario) return <Navigate to="/login" replace state={{ desde: location.pathname }} />;
  if (!tieneRol(...roles)) {
    return <Aviso tipo="error">No tienes permiso para ver esta sección (se requiere rol {roles.join(" o ")}).</Aviso>;
  }
  return <>{children}</>;
}
