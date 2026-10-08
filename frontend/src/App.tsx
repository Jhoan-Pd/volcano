import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import Layout from "./components/Layout";
import RutaProtegida from "./components/RutaProtegida";
import { AuthProvider } from "./context/AuthContext";
import { ThemeProvider } from "./context/ThemeContext";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import { Spinner } from "./components/ui";

// Los paneles privados se cargan bajo demanda: el dashboard público descarga menos JavaScript
const AdminPage = lazy(() => import("./pages/AdminPage"));
const FarmaciaPage = lazy(() => import("./pages/FarmaciaPage"));

function NoEncontrada() {
  return <p className="py-20 text-center text-ink-2">Página no encontrada.</p>;
}

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Suspense fallback={<Spinner />}>
          <Routes>
            <Route element={<Layout />}>
              <Route index element={<DashboardPage />} />
              <Route path="login" element={<LoginPage />} />
              <Route path="farmacia" element={<RutaProtegida roles={["FARMACIA", "ADMIN"]}><FarmaciaPage /></RutaProtegida>} />
              <Route path="admin" element={<RutaProtegida roles={["ADMIN"]}><AdminPage /></RutaProtegida>} />
              <Route path="*" element={<NoEncontrada />} />
            </Route>
          </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
