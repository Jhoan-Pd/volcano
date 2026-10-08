import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { guardarToken, leerToken } from "../api/cliente";
import { authApi } from "../api/servicios";
import type { Rol, Usuario } from "../api/tipos";

interface AuthValor {
  usuario: Usuario | null;
  cargando: boolean;
  login: (email: string, password: string) => Promise<Usuario>;
  logout: () => void;
  tieneRol: (...roles: Rol[]) => boolean;
}

const AuthContext = createContext<AuthValor | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [usuario, setUsuario] = useState<Usuario | null>(null);
  const [cargando, setCargando] = useState(true);

  // Al recargar la página se valida el token guardado contra /auth/me
  useEffect(() => {
    if (!leerToken()) {
      setCargando(false);
      return;
    }
    authApi.me().then(setUsuario).catch(() => guardarToken(null)).finally(() => setCargando(false));
  }, []);

  useEffect(() => {
    const expiro = () => setUsuario(null);
    window.addEventListener("sesion-expirada", expiro);
    return () => window.removeEventListener("sesion-expirada", expiro);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { access_token, usuario: u } = await authApi.login(email, password);
    guardarToken(access_token);
    setUsuario(u);
    return u;
  }, []);

  const logout = useCallback(() => {
    guardarToken(null);
    setUsuario(null);
  }, []);

  const tieneRol = useCallback((...roles: Rol[]) => !!usuario && roles.includes(usuario.rol), [usuario]);

  const valor = useMemo(() => ({ usuario, cargando, login, logout, tieneRol }), [usuario, cargando, login, logout, tieneRol]);
  return <AuthContext.Provider value={valor}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth debe usarse dentro de <AuthProvider>");
  return ctx;
}
