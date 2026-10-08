import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

type Tema = "claro" | "oscuro";
const ThemeContext = createContext<{ tema: Tema; alternar: () => void } | null>(null);

function temaInicial(): Tema {
  return document.documentElement.classList.contains("dark") ? "oscuro" : "claro";
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [tema, setTema] = useState<Tema>(temaInicial);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", tema === "oscuro");
    try {
      localStorage.setItem("tema", tema);
    } catch {
      /* sin almacenamiento: el tema solo dura la sesión */
    }
  }, [tema]);

  return (
    <ThemeContext.Provider value={{ tema, alternar: () => setTema((t) => (t === "claro" ? "oscuro" : "claro")) }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTema() {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTema debe usarse dentro de <ThemeProvider>");
  return ctx;
}
