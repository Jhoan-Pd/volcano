import { LogIn, UserPlus } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { mensajeError } from "../api/cliente";
import { authApi, catalogoApi } from "../api/servicios";
import type { Municipio } from "../api/tipos";
import TituloRevelado from "../components/TituloRevelado";
import { Aviso, Boton, Card, claseInput, Etiqueta } from "../components/ui";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login, usuario } = useAuth();
  const navigate = useNavigate();
  const desde = (useLocation().state as { desde?: string } | null)?.desde;
  const [modo, setModo] = useState<"login" | "registro">("login");
  const [nombre, setNombre] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [municipioId, setMunicipioId] = useState<number | "">("");
  const [municipios, setMunicipios] = useState<Municipio[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  useEffect(() => {
    if (modo === "registro" && municipios.length === 0) {
      catalogoApi.municipios().then((ms) => setMunicipios(ms.filter((m) => m.activo))).catch(() => undefined);
    }
  }, [modo, municipios.length]);

  // Destino según el rol (si venía de una ruta protegida, se regresa allí)
  const destino = (rol: string) => desde ?? (rol === "ADMIN" ? "/admin" : rol === "FARMACIA" ? "/farmacia" : "/");
  if (usuario) return <Navigate to={destino(usuario.rol)} replace />;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    setError(null); setOk(null); setEnviando(true);
    try {
      if (modo === "registro") {
        await authApi.registro({ nombre, email, password, municipio_id: municipioId === "" ? null : municipioId });
        setOk("Cuenta creada. Ya puedes iniciar sesión.");
        setModo("login");
      } else {
        const u = await login(email, password);
        navigate(destino(u.rol), { replace: true });
      }
    } catch (err) {
      setError(mensajeError(err));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="mx-auto max-w-md py-6">
      <Card className="p-6 sm:p-8">
        <TituloRevelado className="titulo-display text-4xl" texto={modo === "login" ? "Iniciar sesión" : "Crear cuenta de ciudadano"} />
        <p className="mt-1 text-sm text-ink-2">
          {modo === "login"
            ? "El dashboard es público; inicia sesión para administrar datos o reportar como farmacia."
            : "Elige tu municipio: te enviaremos por correo las alertas tempranas de riesgo alto o muy alto."}
        </p>
        <form onSubmit={enviar} className="mt-6 space-y-4" noValidate>
          {modo === "registro" && (
            <Etiqueta texto="Nombre completo">
              <input className={claseInput} value={nombre} onChange={(e) => setNombre(e.target.value)} required minLength={3} autoComplete="name" />
            </Etiqueta>
          )}
          {modo === "registro" && (
            <Etiqueta texto="Municipio donde vives" ayuda="Recibirás las alertas de este municipio.">
              <select className={claseInput} value={municipioId} onChange={(e) => setMunicipioId(e.target.value ? Number(e.target.value) : "")}>
                <option value="">Sin municipio (no recibir correos)</option>
                {municipios.map((m) => <option key={m.id} value={m.id}>{m.nombre}</option>)}
              </select>
            </Etiqueta>
          )}
          <Etiqueta texto="Correo electrónico">
            <input className={claseInput} type="email" value={email} onChange={(e) => setEmail(e.target.value)} required autoComplete="email" />
          </Etiqueta>
          <Etiqueta texto="Contraseña" ayuda={modo === "registro" ? "Mínimo 8 caracteres, con letras y números." : undefined}>
            <input className={claseInput} type="password" value={password} onChange={(e) => setPassword(e.target.value)} required minLength={8}
              autoComplete={modo === "login" ? "current-password" : "new-password"} />
          </Etiqueta>
          {error && <Aviso tipo="error">{error}</Aviso>}
          {ok && <Aviso tipo="ok">{ok}</Aviso>}
          <Boton type="submit" className="w-full" cargando={enviando}>
            {modo === "login" ? <><LogIn size={16} /> Ingresar</> : <><UserPlus size={16} /> Crear cuenta</>}
          </Boton>
        </form>
        <button onClick={() => { setModo(modo === "login" ? "registro" : "login"); setError(null); }}
          className="mt-4 w-full text-center text-sm text-accent hover:underline">
          {modo === "login" ? "¿No tienes cuenta? Regístrate como ciudadano" : "Ya tengo cuenta"}
        </button>
      </Card>
      <p className="mt-4 text-center text-xs text-muted">
        Usuarios de demostración del seed: <b>admin@predictor.co</b>, <b>farmacia@demo.co</b>, <b>ciudadano@demo.co</b> (contraseñas en el README).
      </p>
    </div>
  );
}
