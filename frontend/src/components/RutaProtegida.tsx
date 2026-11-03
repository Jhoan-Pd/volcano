"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import type { Rol } from "@/api/tipos";
import { useAuth } from "@/context/AuthContext";
import { Aviso, Spinner } from "./ui";

/**
 * Protege páginas por rol en el navegador (las páginas privadas son CSR: el token vive en
 * localStorage, que el servidor no ve). El backend valida de nuevo: esto solo mejora la experiencia.
 */
export default function RutaProtegida({ roles, children }: { roles: Rol[]; children: ReactNode }) {
  const { usuario, cargando, tieneRol } = useAuth();
  const router = useRouter();
  const ruta = usePathname();

  useEffect(() => {
    if (!cargando && !usuario) router.replace(`/login?desde=${encodeURIComponent(ruta)}`);
  }, [cargando, usuario, router, ruta]);

  if (cargando || !usuario) return <Spinner texto="Verificando sesión…" />;
  if (!tieneRol(...roles)) {
    return <Aviso tipo="error">No tienes permiso para ver esta sección (se requiere rol {roles.join(" o ")}).</Aviso>;
  }
  return <>{children}</>;
}
