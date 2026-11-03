"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Tema = "claro" | "oscuro";
const ThemeContext = createContext<{ tema: Tema; alternar: () => void } | null>(null);

/**
 * El script de <head> (layout.tsx) pone la clase `dark` antes de pintar. El servidor no sabe
 * qué tema eligió el usuario, así que el estado empieza vacío y se lee de <html> al montar:
 * así el HTML del servidor y el primer render del cliente coinciden (sin error de hidratación).
 */
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema | null>(null);

  useEffect(() => {
    setTema(document.documentElement.classList.contains("dark") ? "oscuro" : "claro");
  }, []);

  useEffect(() => {
    if (!tema) return;
    document.documentElement.classList.toggle("dark", tema === "oscuro");
    try {
      localStorage.setItem("tema", tema);
    } catch {
      /* sin almacenamiento: el tema solo dura la sesión */
    }
  }, [tema]);

  return (
    <ThemeContext.Provider value={{ tema: tema ?? "claro", alternar: () => setTema((t) => (t === "oscuro" ? "claro" : "oscuro")) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTema() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTema debe usarse dentro de <ThemeProvider>");
  return ctx;
}
