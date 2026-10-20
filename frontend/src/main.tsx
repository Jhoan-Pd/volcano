import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import App from "./App";
// Tipografías libres (OFL) servidas desde el propio sitio, sin depender de Google Fonts
import "@fontsource-variable/bricolage-grotesque/standard.css"; // títulos (ejes de peso y ancho)
import "@fontsource-variable/hanken-grotesk"; // texto
import "@fontsource-variable/geist"; // cifras grandes
import "./index.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
