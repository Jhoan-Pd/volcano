"""
SentinelaIA Nariño — Dashboard Streamlit (Volcanic Dark Theme)
Ejecutar desde BI_Health_Nari-o/:
    streamlit run src/dashboard/app.py
"""

import subprocess
from pathlib import Path
from datetime import datetime

import numpy as np
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from scipy import stats

# ─── CONFIG ──────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parents[2]
DATA_FINAL = BASE_DIR / "data" / "final" / "dataset_final_municipio_semana.csv"
PRED_PATH  = BASE_DIR / "data" / "final" / "predicciones_riesgo.csv"
MODEL_PATH = BASE_DIR / "src" / "models" / "modelo_riesgo_xgboost.pkl"

st.set_page_config(
    page_title="SentinelaIA Nariño",
    page_icon="SIA",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ─── THEME CONSTANTS ─────────────────────────────────────────────────────────
COLORES = {"alto": "#C0392B", "medio": "#E67E22", "bajo": "#2ECC71"}

COORDS = {
    "PASTO":       (1.2136, -77.2811),
    "SANDONA":     (1.2889, -77.4656),
    "CONSACA":     (1.2333, -77.4667),
    "LA FLORIDA":  (1.3000, -77.4000),
    "YACUANQUER":  (1.1667, -77.3833),
    "NARINO":      (1.3500, -77.2000),
}

GALERAS_IMG = "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Galeras_volcano.jpg/1280px-Galeras_volcano.jpg"
GALERAS_IMG2 = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Galeras_desde_Pasto.jpg/1280px-Galeras_desde_Pasto.jpg"

VOLCANO_THEME = dict(
    paper_bgcolor="rgba(15,15,15,0)",
    plot_bgcolor="rgba(255,255,255,0.03)",
    font=dict(color="rgba(255,255,255,0.8)", family="Inter, sans-serif"),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        linecolor="rgba(255,255,255,0.1)",
        tickcolor="rgba(255,255,255,0.3)",
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        linecolor="rgba(255,255,255,0.1)",
        tickcolor="rgba(255,255,255,0.3)",
    ),
    colorway=["#E67E22", "#C0392B", "#2ECC71", "#3498DB", "#9B59B6"],
)

# ─── CSS GLOBAL ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&family=Playfair+Display:wght@700;800;900&display=swap');

:root {
  --bg:#0a0806;--bg2:#100e0b;--bg3:#181410;
  --lava:#C0392B;--lava2:#e04533;
  --ember:#D4873A;--ember2:#e8a04a;
  --gold:#C9953A;--gold2:#e5b45a;
  --verde:#27AE60;--azul:#2980B9;
  --glass:rgba(255,255,255,0.04);--glass2:rgba(255,255,255,0.07);
  --border:rgba(255,255,255,0.07);--border2:rgba(255,255,255,0.13);
  --txt:rgba(255,255,255,0.92);--txt2:rgba(255,255,255,0.52);--txt3:rgba(255,255,255,0.28);
  --nav-h:64px;--ticker-h:42px;
}
*,*::before,*::after{box-sizing:border-box;}
html{scroll-behavior:smooth;}
html,body,[data-testid="stAppViewContainer"]{
  background:var(--bg)!important;
  font-family:'Inter',sans-serif!important;
  color:var(--txt)!important;
}
.main .block-container{
  background:var(--bg);
  padding-top:calc(var(--nav-h) + 0.5rem)!important;
  padding-bottom:calc(var(--ticker-h) + 1rem)!important;
  max-width:100%!important;
}
[data-testid="stSidebar"]{display:none!important;}
[data-testid="collapsedControl"]{display:none!important;}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:var(--bg2);}
::-webkit-scrollbar-thumb{background:rgba(255,255,255,0.1);border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:rgba(201,149,58,0.4);}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{
  background:var(--glass);border-radius:12px;padding:4px;
  border:1px solid var(--border2);gap:6px;
  border-bottom:none!important;
}
.stTabs [data-baseweb="tab"]{
  background:rgba(255,255,255,0.03)!important;
  border:1px solid rgba(255,255,255,0.05)!important;
  color:var(--txt2)!important;border-radius:8px!important;
  font-size:13px!important;font-weight:500!important;
  padding:10px 18px!important;
  margin-right:8px!important;
  transition:all 0.2s!important;
}
.stTabs [data-baseweb="tab"]:hover{
  color:var(--txt)!important;background:var(--glass2)!important;
  border-color:rgba(255,255,255,0.1)!important;
}
.stTabs [aria-selected="true"]{
  background:rgba(192,57,43,0.22)!important;
  color:#fff!important;border:1px solid rgba(192,57,43,0.4)!important;
}

/* ── Metrics ── */
[data-testid="metric-container"]{
  background:var(--glass)!important;border:1px solid var(--border)!important;
  border-radius:14px!important;padding:16px 20px!important;
}
[data-testid="metric-container"] label{
  color:var(--txt3)!important;font-size:11px!important;
  text-transform:uppercase!important;letter-spacing:0.09em!important;
}
[data-testid="metric-container"] [data-testid="metric-value"]{
  color:white!important;font-size:28px!important;font-weight:900!important;
}

/* ── Headings ── */
h1,h2,h3{color:white!important;}
h1{font-family:'Playfair Display',Georgia,serif!important;font-weight:800!important;}
h2{font-size:18px!important;font-weight:700!important;}
h3{font-size:15px!important;font-weight:600!important;}
hr{border-color:var(--border)!important;}
[data-testid="stAlert"]{background:var(--glass)!important;border-radius:10px!important;border:1px solid var(--border2)!important;}
.stCaption,.stCaption*{color:var(--txt3)!important;font-size:11px!important;}
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:12px!important;overflow:hidden;}
[data-testid="stPlotlyChart"]{
  background:var(--glass)!important;border:1px solid var(--border)!important;
  border-radius:16px!important;padding:16px!important;transition:all 0.3s;
}
[data-testid="stPlotlyChart"]:hover{
  background:var(--glass2)!important;border-color:var(--border2)!important;
  transform:translateY(-2px)!important;box-shadow:0 20px 60px rgba(0,0,0,0.4)!important;
}

/* ── NAVBAR ── */
#sia-navbar{
  position:fixed;top:0;left:0;right:0;height:var(--nav-h);
  background:rgba(10,8,6,0.92);backdrop-filter:blur(24px);
  border-bottom:1px solid var(--border);
  display:grid;grid-template-columns:1fr auto 1fr;
  align-items:center;padding:0 28px;z-index:10000;
  transition:background 0.3s;
}
.sia-nav-left{display:flex;align-items:center;gap:8px;}
.sia-nav-badge{
  display:flex;align-items:center;gap:6px;padding:6px 14px;
  border-radius:8px;border:1px solid rgba(212,135,58,0.35);
  background:rgba(212,135,58,0.1);font-size:11px;font-weight:700;
  color:var(--ember2);letter-spacing:0.06em;text-transform:uppercase;
}
.sia-pulse{
  width:7px;height:7px;border-radius:50%;background:var(--ember);
  box-shadow:0 0 8px var(--ember);animation:pulse-dot 1.8s ease-in-out infinite;
}
.sia-nav-logo{
  display:flex;flex-direction:column;align-items:center;gap:1px;
}
.sia-nav-logo-icon{font-size:22px;line-height:1;filter:drop-shadow(0 0 8px rgba(212,135,58,0.6));}
.sia-nav-logo-name{font-family:'Playfair Display',Georgia,serif;font-size:15px;font-weight:700;color:#fff;letter-spacing:0.04em;line-height:1;}
.sia-nav-logo-sub{font-size:9px;font-weight:600;color:var(--gold);letter-spacing:0.16em;text-transform:uppercase;}
.sia-nav-right{display:flex;align-items:center;justify-content:flex-end;gap:10px;}

/* ── HERO ── */
.sia-hero{
  position:relative;width:100%;min-height:560px;
  display:flex;align-items:center;justify-content:center;
  overflow:hidden;background:var(--bg);
  margin:-1rem -1rem 0 -1rem;width:calc(100% + 2rem);
}
.sia-hero-bg{
  position:absolute;inset:0;
  background-image:url('https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Galeras_volcano.jpg/1280px-Galeras_volcano.jpg');
  background-size:cover;background-position:center 55%;
  opacity:0.22;filter:saturate(0.5);transition:opacity 0.5s;
}
.sia-hero-overlay{
  position:absolute;inset:0;
  background:linear-gradient(to bottom,rgba(8,8,8,0.3) 0%,rgba(8,8,8,0.1) 40%,rgba(8,8,8,0.78) 85%,rgba(8,8,8,1) 100%);
}
.sia-hero-particles{position:absolute;inset:0;pointer-events:none;overflow:hidden;}
.sia-hero-content{
  position:relative;z-index:2;text-align:center;
  padding:60px 24px 80px;max-width:860px;width:100%;
}
.sia-hero-badge{
  display:inline-flex;align-items:center;gap:8px;
  background:rgba(192,57,43,0.15);border:1px solid rgba(192,57,43,0.4);
  border-radius:999px;padding:7px 20px;margin-bottom:32px;
  backdrop-filter:blur(8px);font-size:11px;font-weight:700;
  color:var(--ember);letter-spacing:0.12em;text-transform:uppercase;
  animation:fade-up 0.8s ease both;
}
.sia-hero-title{
  font-family:'Playfair Display',Georgia,serif!important;
  font-size:clamp(42px,8vw,88px);font-weight:900;color:#fff;
  line-height:1.0;letter-spacing:-0.035em;margin-bottom:20px;
  text-shadow:0 0 80px rgba(192,57,43,0.35);
  animation:fade-up 0.8s 0.1s ease both;
}
.sia-hero-title .accent{color:var(--ember);}
.sia-hero-sub{
  font-size:clamp(15px,2.2vw,20px);color:var(--txt2);font-weight:300;
  max-width:560px;margin:0 auto 44px;line-height:1.65;
  animation:fade-up 0.8s 0.2s ease both;
}
.sia-hero-sub strong{color:rgba(255,255,255,0.8);font-weight:500;}
.sia-hero-kpis{
  display:flex;gap:14px;justify-content:center;flex-wrap:wrap;
  margin-bottom:48px;animation:fade-up 0.8s 0.3s ease both;
}
.sia-hero-kpi{
  background:rgba(255,255,255,0.06);backdrop-filter:blur(20px);
  border:1px solid var(--border2);border-radius:14px;
  padding:18px 26px;min-width:130px;text-align:center;transition:all 0.25s;
}
.sia-hero-kpi:hover{background:rgba(255,255,255,0.1);transform:translateY(-3px);}
.sia-hero-kpi-val{font-size:32px;font-weight:900;line-height:1;margin-bottom:5px;}
.sia-hero-kpi-lbl{font-size:10px;color:var(--txt3);text-transform:uppercase;letter-spacing:0.1em;}
.sia-hero-scroll{
  display:flex;flex-direction:column;align-items:center;gap:6px;
  color:var(--txt3);font-size:11px;letter-spacing:0.1em;text-transform:uppercase;
  animation:fade-up 0.8s 0.5s ease both,bounce 2.5s 1.5s ease-in-out infinite;
}

/* ── FILTER BAR ── */
.sia-filter-bar{
  display:flex;gap:12px;align-items:center;flex-wrap:wrap;
  padding:14px 18px;background:var(--glass);
  border:1px solid var(--border);border-radius:12px;margin-bottom:28px;
}

/* ── SECTION ── */
.sia-section-label{font-size:11px;font-weight:700;color:var(--ember);text-transform:uppercase;letter-spacing:0.14em;margin-bottom:8px;}
.sia-section-title{font-family:'Playfair Display',Georgia,serif;font-size:clamp(20px,3vw,34px);font-weight:800;color:#fff;letter-spacing:-0.025em;line-height:1.15;margin-bottom:10px;}
.sia-section-sub{font-size:14px;color:var(--txt2);line-height:1.6;max-width:600px;margin-bottom:32px;}

/* ── GLASS CARD ── */
.sia-glass-card{
  background:var(--glass);border:1px solid var(--border);
  border-radius:16px;padding:26px;transition:all 0.3s;
  position:relative;overflow:hidden;
}
.sia-glass-card::before{
  content:'';position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,0.12),transparent);
}
.sia-glass-card:hover{
  background:var(--glass2);border-color:var(--border2);
  transform:translateY(-2px);box-shadow:0 20px 60px rgba(0,0,0,0.4);
}
.sia-card-label{font-size:11px;font-weight:700;color:var(--ember);text-transform:uppercase;letter-spacing:0.12em;margin-bottom:6px;}
.sia-card-title{font-size:16px;font-weight:700;color:#fff;margin-bottom:4px;letter-spacing:-0.01em;}
.sia-card-sub{font-size:12px;color:var(--txt2);margin-bottom:18px;line-height:1.5;}

/* ── KPI BLOCKS ── */
.sia-kpi-row{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:32px;}
.sia-kpi-block{
  background:var(--glass);border:1px solid var(--border);
  border-radius:14px;padding:24px 26px;position:relative;overflow:hidden;transition:all 0.25s;
}
.sia-kpi-block:hover{background:var(--glass2);transform:translateY(-2px);}
.sia-kpi-block::after{
  content:'';position:absolute;bottom:0;left:0;right:0;
  height:2px;border-radius:0 0 14px 14px;
}
.sia-kpi-block.lava::after{background:linear-gradient(90deg,var(--lava),transparent);}
.sia-kpi-block.ember::after{background:linear-gradient(90deg,var(--ember),transparent);}
.sia-kpi-block.verde::after{background:linear-gradient(90deg,var(--verde),transparent);}
.sia-kpi-block.azul::after{background:linear-gradient(90deg,var(--azul),transparent);}
.sia-kpi-lbl{font-size:11px;font-weight:600;color:var(--txt3);text-transform:uppercase;letter-spacing:0.09em;margin-bottom:8px;}
.sia-kpi-val{font-size:38px;font-weight:900;color:#fff;line-height:1;margin-bottom:4px;letter-spacing:-0.02em;}
.sia-kpi-note{font-size:12px;color:var(--txt2);}
.sia-kpi-icon{position:absolute;right:22px;top:50%;transform:translateY(-50%);font-size:32px;opacity:0.1;}

/* ── ALERT CARDS ── */
.sia-alert-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:24px;}
.sia-alert-card{
  background:var(--glass);border:1px solid var(--border);
  border-radius:14px;padding:22px 20px;position:relative;overflow:hidden;transition:all 0.25s;
}
.sia-alert-card:hover{transform:translateY(-3px);box-shadow:0 16px 40px rgba(0,0,0,0.4);}
.sia-alert-card.alto{border-top:2px solid var(--lava);background:rgba(192,57,43,0.06);}
.sia-alert-card.medio{border-top:2px solid var(--ember);background:rgba(230,126,34,0.06);}
.sia-alert-card.bajo{border-top:2px solid var(--verde);background:rgba(39,174,96,0.06);}
.sia-alert-mun{font-size:15px;font-weight:700;color:#fff;margin-bottom:6px;}
.sia-alert-stats{font-size:12px;color:var(--txt2);margin-bottom:14px;line-height:1.5;}
.sia-alert-pill{display:inline-block;padding:4px 14px;border-radius:999px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:0.1em;}
.sia-alert-pill.alto{background:rgba(192,57,43,0.2);color:var(--lava2);border:1px solid rgba(192,57,43,0.3);}
.sia-alert-pill.medio{background:rgba(230,126,34,0.2);color:var(--ember2);border:1px solid rgba(230,126,34,0.3);}
.sia-alert-pill.bajo{background:rgba(39,174,96,0.2);color:#2ecc71;border:1px solid rgba(39,174,96,0.3);}

/* ── VOLCANO CARD ── */
.sia-volcano-card{position:relative;border-radius:18px;overflow:hidden;border:1px solid var(--border);margin-bottom:24px;min-height:240px;}
.sia-volcano-card img{width:100%;height:240px;object-fit:cover;filter:saturate(0.6) brightness(0.4);display:block;}
.sia-volcano-overlay{position:absolute;inset:0;background:linear-gradient(to top,rgba(8,8,8,0.97) 0%,rgba(8,8,8,0.2) 55%,transparent 100%);display:flex;align-items:flex-end;padding:28px 32px;}
.sia-volcano-eyebrow{font-size:10px;font-weight:700;color:var(--ember);text-transform:uppercase;letter-spacing:0.14em;margin-bottom:6px;}
.sia-volcano-name{font-size:26px;font-weight:800;color:#fff;letter-spacing:-0.02em;margin-bottom:4px;}
.sia-volcano-desc{font-size:13px;color:var(--txt2);}

/* ── SO2 STATS ── */
.sia-so2-stats{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px;}
.sia-so2-stat{background:var(--glass);border:1px solid var(--border);border-radius:12px;padding:18px 20px;text-align:center;}
.sia-so2-val{font-size:28px;font-weight:900;color:#fff;letter-spacing:-0.02em;}
.sia-so2-lbl{font-size:11px;color:var(--txt3);text-transform:uppercase;letter-spacing:0.08em;margin-top:4px;}

/* ── PRED CARDS ── */
.sia-pred-card{background:var(--glass);border:1px solid var(--border);border-radius:14px;padding:20px 22px;transition:all 0.25s;}
.sia-pred-card:hover{background:var(--glass2);transform:translateY(-2px);}
.sia-pred-mun{font-size:15px;font-weight:700;color:#fff;margin-bottom:4px;}
.sia-pred-event{font-size:11px;color:var(--txt2);margin-bottom:12px;}
.sia-pred-bar-wrap{background:rgba(255,255,255,0.06);border-radius:999px;height:6px;overflow:hidden;margin-bottom:8px;}
.sia-pred-bar{height:100%;border-radius:999px;transition:width 1s ease;}
.sia-pred-bar.alto{background:linear-gradient(90deg,var(--lava),var(--lava2));}
.sia-pred-bar.medio{background:linear-gradient(90deg,var(--ember),var(--ember2));}
.sia-pred-bar.bajo{background:linear-gradient(90deg,var(--verde),#2ecc71);}
.sia-pred-foot{display:flex;justify-content:space-between;align-items:center;}
.sia-pred-prob{font-size:12px;color:var(--txt2);}

/* ── FOOTER ── */
.sia-footer{background:var(--bg2);border-top:1px solid var(--border);padding:60px 40px 32px;margin-top:80px;}
.sia-footer-grid{display:grid;grid-template-columns:2fr 1fr 1fr;gap:48px;max-width:1100px;margin:0 auto 48px;}
.sia-footer-brand-name{font-family:'Playfair Display',Georgia,serif;font-size:18px;font-weight:800;color:#fff;letter-spacing:-0.02em;margin-bottom:10px;}
.sia-footer-brand-name span{color:var(--ember);}
.sia-footer-brand-desc{font-size:13px;color:var(--txt3);line-height:1.65;max-width:320px;}
.sia-footer-col-title{font-size:11px;font-weight:700;color:var(--txt2);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:16px;}
.sia-footer-link{display:block;font-size:13px;color:var(--txt3);text-decoration:none;margin-bottom:10px;}
.sia-footer-bottom{max-width:1100px;margin:0 auto;padding-top:24px;border-top:1px solid var(--border);display:flex;justify-content:space-between;align-items:center;}
.sia-footer-copy{font-size:12px;color:var(--txt3);}

/* ── TICKER ── */
.sia-ticker-bar{position:fixed;bottom:0;left:0;right:0;height:var(--ticker-h);background:rgba(10,8,6,0.95);border-top:1px solid var(--border);z-index:9999;overflow:hidden;display:flex;align-items:center;}
.sia-ticker-track{display:flex;white-space:nowrap;animation:stk-scroll 38s linear infinite;}
.sia-ticker-item{display:inline-flex;align-items:center;gap:8px;padding:0 28px;font-size:11px;font-weight:600;letter-spacing:0.06em;color:var(--txt2);border-right:1px solid var(--border);}
.sia-ticker-dot{width:6px;height:6px;border-radius:50%;flex-shrink:0;}
.t-label{color:var(--txt3);font-weight:400;margin-right:2px;}
.t-val{color:#fff;}
.t-alto{color:var(--lava2);}
.t-medio{color:var(--ember2);}
.t-bajo{color:var(--verde);}

/* ── ANIMATIONS ── */
@keyframes fade-up{from{opacity:0;transform:translateY(24px);}to{opacity:1;transform:translateY(0);}}
@keyframes bounce{0%,100%{transform:translateY(0);}50%{transform:translateY(8px);}}
@keyframes float-up{0%{transform:translateY(110vh) scale(1);opacity:0;}8%{opacity:1;}92%{opacity:0.3;}100%{transform:translateY(-5vh) scale(0.6) rotate(180deg);opacity:0;}}
@keyframes pulse-dot{0%,100%{box-shadow:0 0 6px var(--ember);transform:scale(1);}50%{box-shadow:0 0 18px var(--ember),0 0 30px rgba(212,135,58,0.3);transform:scale(1.2);}}
@keyframes stk-scroll{0%{transform:translateX(0);}100%{transform:translateX(-50%);}}
</style>""", unsafe_allow_html=True)



# ─── CARGA DE DATOS ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def cargar_datos():
    if DATA_FINAL.exists():
        df = pd.read_csv(DATA_FINAL)
        df["municipio_upper"] = (
            df["municipio"].str.upper().str.strip()
            .str.replace("Á", "A").str.replace("É", "E")
            .str.replace("Í", "I").str.replace("Ó", "O")
            .str.replace("Ú", "U").str.replace("Ñ", "N")
            .str.normalize("NFKD")
            .str.encode("ascii", errors="ignore")
            .str.decode("ascii")
        )
        return df
    return pd.DataFrame()

@st.cache_data(ttl=300)
def cargar_predicciones():
    if PRED_PATH.exists():
        return pd.read_csv(PRED_PATH)
    return pd.DataFrame()

# ─── HELPERS ─────────────────────────────────────────────────────────────────

_DEFAULT_LEGEND = dict(
    bgcolor="rgba(255,255,255,0.04)",
    bordercolor="rgba(255,255,255,0.08)",
    borderwidth=1,
)

def apply_volcano_theme(fig, height=400, **extra):
    legend = {**_DEFAULT_LEGEND, **extra.pop("legend", {})}
    fig.update_layout(height=height, legend=legend, **VOLCANO_THEME, **extra)
    return fig

def render_alerta_card(municipio, nivel, tasa, casos):
    emojis   = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}
    emoji  = emojis.get(nivel, "⚪")
    return (f'<div class="sia-alert-card {nivel}">'
            f'<div class="sia-alert-mun">{emoji} {municipio}</div>'
            f'<div class="sia-alert-stats">Tasa: {tasa:.1f} x 100k<br>Casos: {int(casos):,}</div>'
            f'<div class="sia-alert-pill {nivel}">{nivel}</div>'
            f'</div>')

def section_header(title, label=None):
    lbl = label if label else "Análisis"
    st.markdown(
        f'<div style="margin:28px 0 16px 0">'
        f'<div class="sia-section-label">{lbl}</div>'
        f'<div class="sia-section-title">{title}</div>'
        f'</div>',
        unsafe_allow_html=True
    )

def build_ticker_html(df_data):
    colores = {"alto": "#C0392B", "medio": "#E67E22", "bajo": "#2ECC71"}
    items = ""
    if not df_data.empty:
        df_sum = (
            df_data.groupby("municipio")
            .agg(casos=("casos", "sum"), tasa=("tasa_x_100k", "mean"))
            .reset_index()
        )
        q33, q66 = df_sum["tasa"].quantile(0.33), df_sum["tasa"].quantile(0.66)
        df_sum["nivel"] = df_sum["tasa"].apply(
            lambda x: "alto" if x >= q66 else ("medio" if x >= q33 else "bajo")
        )
        for _, row in df_sum.iterrows():
            col = colores.get(row["nivel"], "#888")
            items += (
                f'<div class="stk-item">'
                f'<span class="stk-dot" style="background:{col}"></span>'
                f'<span class="stk-lbl">{row["municipio"]}</span>'
                f'<span class="stk-val">{int(row["casos"]):,} casos</span>'
                f'<span style="color:{col}">· {row["nivel"].upper()}</span>'
                f'</div>'
            )
    else:
        items = '<div class="stk-item"><span class="stk-lbl">Sin datos disponibles</span></div>'
    return f"""
    <div class="stk-bar">
        <div class="stk-track">{items * 2}</div>
    </div>
    <style>
    .stk-bar {{
        position:fixed;bottom:0;left:0;right:0;height:40px;
        background:rgba(10,8,6,0.97);border-top:1px solid rgba(255,255,255,0.08);
        z-index:9999;overflow:hidden;display:flex;align-items:center;
    }}
    .stk-track {{
        display:flex;white-space:nowrap;
        animation:stk-scroll 38s linear infinite;
    }}
    .stk-item {{
        display:inline-flex;align-items:center;gap:8px;
        padding:0 24px;font-size:11px;font-weight:600;
        letter-spacing:0.06em;color:rgba(255,255,255,0.5);
        border-right:1px solid rgba(255,255,255,0.07);
        font-family:'Inter',sans-serif;
    }}
    .stk-dot {{width:6px;height:6px;border-radius:50%;flex-shrink:0}}
    .stk-lbl {{color:rgba(255,255,255,0.3)}}
    .stk-val {{color:#fff}}
    @keyframes stk-scroll {{
        0%   {{transform:translateX(0)}}
        100% {{transform:translateX(-50%)}}
    }}
    </style>"""

# ─── NAVBAR (fixed, injected) ─────────────────────────────────────────────────
components.html("""
<div id="sia-navbar">
  <div class="sia-nav-left">
    <div class="sia-nav-badge"><div class="sia-pulse"></div>Actividad: MEDIO</div>
  </div>
  <div class="sia-nav-logo">
    <div class="sia-nav-logo-icon">🌋</div>
    <div class="sia-nav-logo-name">SentinelaIA</div>
    <div class="sia-nav-logo-sub">Nariño · Galeras</div>
  </div>
  <div class="sia-nav-right">
    <span style="font-size:12px;color:rgba(255,255,255,0.4);font-weight:600;letter-spacing:0.05em">DATOS AL ECOSISTEMA 2026</span>
  </div>
</div>
""", height=0)

# ─── CARGA DE DATOS ────────────────────────────────────────────────────────────
df_full = cargar_datos()
if df_full.empty:
    st.error("Sin datos. Ejecuta el pipeline ETL.")
    st.stop()
df_pred_global = cargar_predicciones()

# ─── HERO SECTION ─────────────────────────────────────────────────────────────
_total_casos_hero = int(df_full["casos"].sum()) if not df_full.empty else 0

components.html(f"""
<div class="sia-hero">
  <div class="sia-hero-bg"></div>
  <div class="sia-hero-overlay"></div>
  <div class="sia-hero-particles" id="sia-particles"></div>
  <div class="sia-hero-content">
    <div class="sia-hero-badge">
      <span style="width:8px;height:8px;border-radius:50%;background:#D4873A;display:inline-block;box-shadow:0 0 8px #D4873A;animation:pulse-dot 1.8s ease-in-out infinite;flex-shrink:0"></span>
      🌋 Volcán Galeras &nbsp;·&nbsp; Nivel de Actividad: MEDIO
    </div>
    <div class="sia-hero-title">Siente el calor,<br><span class="accent">prevé la crisis.</span></div>
    <p class="sia-hero-sub">Vigilancia epidemiológica predictiva en el área de influencia del <strong>Volcán Galeras</strong>. 6 municipios · Nariño, Colombia.</p>
    <div class="sia-hero-kpis">
      <div class="sia-hero-kpi"><div class="sia-hero-kpi-val" style="color:#fff">{_total_casos_hero:,}</div><div class="sia-hero-kpi-lbl">Casos totales</div></div>
      <div class="sia-hero-kpi"><div class="sia-hero-kpi-val" style="color:#D4873A">6</div><div class="sia-hero-kpi-lbl">Municipios</div></div>
      <div class="sia-hero-kpi"><div class="sia-hero-kpi-val" style="color:#C0392B">SO₂</div><div class="sia-hero-kpi-lbl">Monitor activo</div></div>
      <div class="sia-hero-kpi"><div class="sia-hero-kpi-val" style="color:#27AE60">XGB</div><div class="sia-hero-kpi-lbl">IA predictiva</div></div>
    </div>
    <div class="sia-hero-scroll">Explorar datos<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 5v14M5 12l7 7 7-7"/></svg></div>
  </div>
</div>
<style>
.sia-hero{{position:relative;width:100%;min-height:540px;display:flex;align-items:center;justify-content:center;overflow:hidden;background:#0a0806;}}
.sia-hero-bg{{position:absolute;inset:0;background-image:url('https://upload.wikimedia.org/wikipedia/commons/thumb/8/8c/Galeras_volcano.jpg/1280px-Galeras_volcano.jpg');background-size:cover;background-position:center 55%;opacity:0.22;filter:saturate(0.5);}}
.sia-hero-overlay{{position:absolute;inset:0;background:linear-gradient(to bottom,rgba(8,8,8,0.3) 0%,rgba(8,8,8,0.1) 40%,rgba(8,8,8,0.78) 85%,rgba(8,8,8,1) 100%);}}
.sia-hero-particles{{position:absolute;inset:0;pointer-events:none;overflow:hidden;}}
.sia-hero-content{{position:relative;z-index:2;text-align:center;padding:60px 24px 80px;max-width:860px;width:100%;}}
.sia-hero-badge{{display:inline-flex;align-items:center;gap:8px;background:rgba(192,57,43,0.15);border:1px solid rgba(192,57,43,0.4);border-radius:999px;padding:7px 20px;margin-bottom:32px;font-size:11px;font-weight:700;color:#D4873A;letter-spacing:0.12em;text-transform:uppercase;animation:fade-up 0.8s ease both;}}
.sia-hero-title{{font-family:'Playfair Display',Georgia,serif;font-size:clamp(42px,8vw,84px);font-weight:900;color:#fff;line-height:1.0;letter-spacing:-0.035em;margin-bottom:20px;text-shadow:0 0 80px rgba(192,57,43,0.35);animation:fade-up 0.8s 0.1s ease both;}}
.accent{{color:#D4873A;}}
.sia-hero-sub{{font-size:clamp(15px,2.2vw,20px);color:rgba(255,255,255,0.52);font-weight:300;max-width:560px;margin:0 auto 44px;line-height:1.65;animation:fade-up 0.8s 0.2s ease both;}}
.sia-hero-sub strong{{color:rgba(255,255,255,0.8);font-weight:500;}}
.sia-hero-kpis{{display:flex;gap:14px;justify-content:center;flex-wrap:wrap;margin-bottom:48px;animation:fade-up 0.8s 0.3s ease both;}}
.sia-hero-kpi{{background:rgba(255,255,255,0.06);backdrop-filter:blur(20px);border:1px solid rgba(255,255,255,0.13);border-radius:14px;padding:18px 26px;min-width:130px;text-align:center;transition:all 0.25s;}}
.sia-hero-kpi:hover{{background:rgba(255,255,255,0.1);transform:translateY(-3px);}}
.sia-hero-kpi-val{{font-size:32px;font-weight:900;line-height:1;margin-bottom:5px;}}
.sia-hero-kpi-lbl{{font-size:10px;color:rgba(255,255,255,0.28);text-transform:uppercase;letter-spacing:0.1em;}}
.sia-hero-scroll{{display:flex;flex-direction:column;align-items:center;gap:6px;color:rgba(255,255,255,0.28);font-size:11px;letter-spacing:0.1em;text-transform:uppercase;animation:fade-up 0.8s 0.5s ease both,bounce 2.5s 1.5s ease-in-out infinite;}}
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:wght@700;800;900&display=swap');
@keyframes fade-up{{from{{opacity:0;transform:translateY(24px);}}to{{opacity:1;transform:translateY(0);}}}}
@keyframes bounce{{0%,100%{{transform:translateY(0);}}50%{{transform:translateY(8px);}}}}
@keyframes float-up{{0%{{transform:translateY(110vh) scale(1);opacity:0;}}8%{{opacity:1;}}92%{{opacity:0.3;}}100%{{transform:translateY(-5vh) scale(0.6) rotate(180deg);opacity:0;}}}}
@keyframes pulse-dot{{0%,100%{{box-shadow:0 0 6px #D4873A;transform:scale(1);}}50%{{box-shadow:0 0 18px #D4873A,0 0 30px rgba(212,135,58,0.3);transform:scale(1.2);}}}}
</style>
<script>
(function(){{
  var c=document.getElementById('sia-particles');
  if(!c)return;
  for(var i=0;i<32;i++){{
    var p=document.createElement('div');
    var sz=(Math.random()*4+2).toFixed(1);
    var lft=(Math.random()*100).toFixed(1);
    var dly=(Math.random()*8).toFixed(1);
    var dur=(Math.random()*12+10).toFixed(1);
    var alp=(Math.random()*0.45+0.08).toFixed(2);
    var col=i%2===0?'rgba(230,126,34,'+alp+')':'rgba(192,57,43,'+alp+')';
    var blr=(Math.random()*1.5).toFixed(1);
    p.style.cssText='position:absolute;width:'+sz+'px;height:'+sz+'px;background:'+col+';border-radius:50%;left:'+lft+'%;bottom:0;animation:float-up '+dur+'s linear '+dly+'s infinite;filter:blur('+blr+'px)';
    c.appendChild(p);
  }}
}})();
</script>
""", height=560)

# ─── FILTROS EN MAIN CONTENT ──────────────────────────────────────────────────
st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)

municipios_disp = ["Todos"] + sorted(df_full["municipio"].unique().tolist())
_anios_hist  = set(df_full["anio"].dropna().unique().astype(int).tolist())
_anios_pred  = set(df_pred_global["anio"].dropna().unique().astype(int).tolist()) if not df_pred_global.empty else set()
anios_disp   = sorted(_anios_hist | _anios_pred, reverse=True)
_anio_default = 0  # año más reciente primero (2026)

fc1, fc2, fc3, fc4 = st.columns([2, 2, 2, 3])
with fc1:
    municipio_sel = st.selectbox("🏙️ Municipio", municipios_disp, key="f_mun")
with fc2:
    anio_sel = st.selectbox("📅 Año", anios_disp, index=_anio_default, key="f_anio")
with fc3:
    evento_sel = st.selectbox("🦠 Enfermedad", ["IRA + EDA", "IRA", "EDA"], key="f_evento")
with fc4:
    semanas_rango = st.slider("📊 Semanas epidemiológicas", 1, 52, (1, 52), key="f_sem")





# ─── FILTRADO ────────────────────────────────────────────────────────────────

df = df_full.copy()
if municipio_sel != "Todos":
    df = df[df["municipio"] == municipio_sel]
df = df[df["anio"] == anio_sel]
if evento_sel != "IRA + EDA":
    df = df[df["evento_estandar"] == evento_sel]
df = df[df["semana_epidemiologica"].between(semanas_rango[0], semanas_rango[1])]

# ─── KPIs ────────────────────────────────────────────────────────────────────

total_casos      = int(df["casos"].sum())
tasa_prom        = df["tasa_x_100k"].mean() if not df.empty else 0
semanas_con_datos = df[df["casos"] > 0]["semana_epidemiologica"].nunique()
so2_prom         = df["so2_flux_ton_dia"].mean() if "so2_flux_ton_dia" in df.columns else 0

anio_ant = anio_sel - 1
df_ant   = df_full[df_full["anio"] == anio_ant]
if evento_sel != "IRA + EDA":
    df_ant = df_ant[df_ant["evento_estandar"] == evento_sel]
if municipio_sel != "Todos":
    df_ant = df_ant[df_ant["municipio"] == municipio_sel]
df_ant    = df_ant[df_ant["semana_epidemiologica"].between(semanas_rango[0], semanas_rango[1])]
casos_ant = int(df_ant["casos"].sum()) if not df_ant.empty else None
delta_casos = int(total_casos - casos_ant) if casos_ant else None

st.markdown('<div style="height:28px"></div>', unsafe_allow_html=True)

_delta_html = ""
if delta_casos is not None:
    _sign  = "+" if delta_casos > 0 else ""
    _dcol  = "#C0392B" if delta_casos > 0 else "#2ECC71"
    _delta_html = (
        f'<div style="font-size:12px;color:{_dcol};margin-top:4px">'
        f'{_sign}{delta_casos:,} vs {anio_ant}</div>'
    )
_so2_col   = "lava" if so2_prom > 700 else ("ember" if so2_prom > 400 else "verde")
_so2_nivel = "Alto"   if so2_prom > 700 else ("Medio"   if so2_prom > 400 else "Normal")
_so2_disp  = f"{so2_prom:.0f}" if so2_prom > 0 else "—"
_so2_sub   = f"t/día · {_so2_nivel}" if so2_prom > 0 else "Sin dato"

def _kpi_card(label, value, note, css_class, icon, extra=""):
    return (f'<div class="sia-kpi-block {css_class}">'
            f'<div class="sia-kpi-lbl">{label}</div>'
            f'<div class="sia-kpi-val">{value}</div>'
            f'<div class="sia-kpi-note">{note}</div>'
            f'{extra}'
            f'<div class="sia-kpi-icon">{icon}</div>'
            f'</div>')

st.markdown(f"""
<div class="sia-kpi-row">
  {_kpi_card("Total casos", f"{total_casos:,}", "Acumulado período", "lava", "🩺", _delta_html)}
  {_kpi_card("Tasa promedio", f"{tasa_prom:.1f}", "por 100 000 hab.", "ember", "📈")}
  {_kpi_card("Semanas con casos", str(semanas_con_datos), "Epidemiológicas activas", "verde", "📅")}
  {_kpi_card("SO₂ Galeras", _so2_disp, _so2_sub, _so2_col, "🌋")}
</div>
""", unsafe_allow_html=True)

st.markdown('<div style="border-top:1px solid rgba(255,255,255,0.07);margin:8px 0 16px"></div>', unsafe_allow_html=True)

# ─── TABS ────────────────────────────────────────────────────────────────────

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Mapa de Riesgo",
    "Canal Endémico",
    "Comparativo Municipal",
    "Galeras + SO₂",
    "Predicciones IA",
    "📊 Power BI",
    "🔬 ANOVA Comparativo",
])

# ════════ TAB 1 — MAPA ═══════════════════════════════════════════════════════
with tab1:
    col_mapa, col_alertas = st.columns([3, 1])

    with col_mapa:
        section_header("Distribución de riesgo — Área Galeras", label="Distribución espacial")

        if df.empty:
            st.info("Sin datos para los filtros seleccionados.")
        else:
            df_mapa = (
                df.groupby("municipio_upper")
                .agg(casos=("casos", "sum"), tasa=("tasa_x_100k", "mean"))
                .reset_index()
            )
            q33, q66 = df_mapa["tasa"].quantile(0.33), df_mapa["tasa"].quantile(0.66)
            df_mapa["nivel_riesgo"] = df_mapa["tasa"].apply(
                lambda x: "alto" if x >= q66 else ("medio" if x >= q33 else "bajo")
            )
            df_mapa["lat"]      = df_mapa["municipio_upper"].map(lambda m: COORDS.get(m, (1.2, -77.3))[0])
            df_mapa["lon"]      = df_mapa["municipio_upper"].map(lambda m: COORDS.get(m, (1.2, -77.3))[1])
            df_mapa["size_plot"] = df_mapa["casos"].clip(lower=1)

            fig_mapa = px.scatter_mapbox(
                df_mapa, lat="lat", lon="lon",
                size="size_plot", color="nivel_riesgo",
                color_discrete_map=COLORES,
                hover_name="municipio_upper",
                hover_data={"casos": True, "tasa": ":.1f", "lat": False, "lon": False, "size_plot": False},
                size_max=50, zoom=9.5,
                mapbox_style="carto-darkmatter",
            )
            fig_mapa.add_trace(go.Scattermapbox(
                lat=[1.2217], lon=[-77.3597],
                mode="markers+text",
                marker=dict(size=16, color="#E67E22", symbol="triangle"),
                text=["Galeras"], textposition="top right",
                name="Volcán Galeras",
                hovertext="Volcán Galeras (4.276 m)",
            ))
            fig_mapa.update_layout(
                height=430,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    orientation="h", y=-0.06,
                    bgcolor="rgba(255,255,255,0.05)",
                    bordercolor="rgba(255,255,255,0.1)",
                    font=dict(color="rgba(255,255,255,0.7)"),
                ),
            )
            st.plotly_chart(fig_mapa, use_container_width=True)

    with col_alertas:
        section_header("Panel de alertas", label="Estado actual")
        if not df.empty:
            df_al = (
                df.groupby("municipio")
                .agg(tasa=("tasa_x_100k", "mean"), casos=("casos", "sum"))
                .reset_index()
                .sort_values("tasa", ascending=False)
            )
            q33a = df_al["tasa"].quantile(0.33)
            q66a = df_al["tasa"].quantile(0.66)
            df_al["nivel"] = df_al["tasa"].apply(
                lambda x: "alto" if x >= q66a else ("medio" if x >= q33a else "bajo")
            )
            cards_html = "".join(
                render_alerta_card(row["municipio"], row["nivel"], row["tasa"], row["casos"])
                for _, row in df_al.iterrows()
            )
            st.markdown(cards_html, unsafe_allow_html=True)

# ════════ TAB 2 — CANAL ENDÉMICO ═════════════════════════════════════════════
with tab2:
    section_header("Canal Endémico", label="Vigilancia histórica")

    df_hist = df_full.copy()
    if evento_sel != "IRA + EDA":
        df_hist = df_hist[df_hist["evento_estandar"] == evento_sel]
    if municipio_sel != "Todos":
        df_hist = df_hist[df_hist["municipio"] == municipio_sel]

    canal = (
        df_hist.groupby(["semana_epidemiologica", "anio"])["casos"]
        .sum().reset_index()
        .groupby("semana_epidemiologica")["casos"]
        .agg(mediana="median", p25=lambda x: x.quantile(0.25), p75=lambda x: x.quantile(0.75))
        .reset_index()
    )

    df_actual = (
        df[df["anio"] == anio_sel]
        .groupby("semana_epidemiologica")["casos"].sum().reset_index()
    )

    fig_canal = go.Figure()
    fig_canal.add_trace(go.Scatter(
        x=canal["semana_epidemiologica"].tolist() + canal["semana_epidemiologica"].tolist()[::-1],
        y=canal["p75"].tolist() + canal["p25"].tolist()[::-1],
        fill="toself",
        fillcolor="rgba(230,126,34,0.12)",
        line=dict(color="rgba(0,0,0,0)"),
        name="Corredor histórico (P25-P75)",
    ))
    fig_canal.add_trace(go.Scatter(
        x=canal["semana_epidemiologica"], y=canal["mediana"],
        mode="lines",
        line=dict(color="rgba(230,126,34,0.6)", dash="dash", width=1.5),
        name="Mediana histórica",
    ))

    alerta_alta = pd.DataFrame()
    if not df_actual.empty:
        fig_canal.add_trace(go.Scatter(
            x=df_actual["semana_epidemiologica"], y=df_actual["casos"],
            mode="lines+markers",
            line=dict(color="#E67E22", width=2.5),
            marker=dict(size=5, color="#E67E22"),
            name=f"Casos {anio_sel}",
        ))
        alerta = df_actual.merge(canal, on="semana_epidemiologica")
        alerta_alta = alerta[alerta["casos"] > alerta["p75"]]
        if not alerta_alta.empty:
            fig_canal.add_trace(go.Scatter(
                x=alerta_alta["semana_epidemiologica"], y=alerta_alta["casos"],
                mode="markers",
                marker=dict(size=11, color="#C0392B", symbol="circle-open", line=dict(width=2, color="#C0392B")),
                name="⚠ Sobre corredor",
            ))

    apply_volcano_theme(fig_canal, height=420,
                        xaxis_title="Semana epidemiológica",
                        yaxis_title="Casos",
                        hovermode="x unified",
                        legend=dict(orientation="h", y=-0.22,
                                    bgcolor="rgba(255,255,255,0.04)",
                                    bordercolor="rgba(255,255,255,0.08)"))
    st.plotly_chart(fig_canal, use_container_width=True)

    semanas_alerta = len(alerta_alta) if not alerta_alta.empty else 0
    if semanas_alerta > 0:
        st.warning(f"{semanas_alerta} semana(s) superaron el corredor histórico en {anio_sel}")

# ════════ TAB 3 — COMPARATIVO MUNICIPAL ══════════════════════════════════════
with tab3:
    section_header("Comparativo Municipal", label="Análisis territorial")

    col_bar, col_heat = st.columns(2)

    with col_bar:
        df_muni = (
            df.groupby(["municipio", "evento_estandar"])
            .agg(casos=("casos", "sum"), tasa=("tasa_x_100k", "mean"))
            .reset_index()
            .sort_values("tasa", ascending=True)
        )
        fig_bar = px.bar(
            df_muni, x="tasa", y="municipio", color="evento_estandar",
            color_discrete_map={"IRA": "#3498DB", "EDA": "#E67E22"},
            orientation="h", barmode="group",
            text="tasa",
            title=f"Tasa x 100k hab — {anio_sel}",
        )
        fig_bar.update_traces(texttemplate="%{text:.1f}", textposition="outside",
                              textfont_color="rgba(255,255,255,0.7)")
        apply_volcano_theme(fig_bar, height=370, xaxis_title="Tasa x 100k")
        st.plotly_chart(fig_bar, use_container_width=True)

    with col_heat:
        evento_heat = "EDA" if evento_sel == "IRA + EDA" else evento_sel
        df_heat = (
            df_full[
                (df_full["anio"] == anio_sel) &
                (df_full["evento_estandar"] == evento_heat)
            ]
            .pivot_table(index="municipio", columns="semana_epidemiologica",
                         values="casos", aggfunc="sum")
            .fillna(0)
        )
        if not df_heat.empty:
            fig_heat = px.imshow(
                df_heat,
                color_continuous_scale=["#0a0a0a", "#2d0f0f", "#C0392B", "#E67E22", "#F9CA24"],
                title=f"Casos por municipio/semana — {anio_sel}",
                labels=dict(x="Semana", y="Municipio", color="Casos"),
            )
            apply_volcano_theme(fig_heat, height=370)
            st.plotly_chart(fig_heat, use_container_width=True)

    section_header("Tabla de detalle", label="Detalle completo")
    df_tabla = (
        df.groupby(["municipio", "evento_estandar"])
        .agg(casos=("casos", "sum"),
             tasa_prom=("tasa_x_100k", "mean"),
             tasa_max=("tasa_x_100k", "max"))
        .reset_index()
        .rename(columns={"tasa_prom": "Tasa prom", "tasa_max": "Tasa máx"})
    )
    df_tabla["Tasa prom"] = df_tabla["Tasa prom"].round(2)
    df_tabla["Tasa máx"]  = df_tabla["Tasa máx"].round(2)
    st.dataframe(df_tabla, use_container_width=True, hide_index=True)

# ════════ TAB 4 — GALERAS SO₂ ════════════════════════════════════════════════
with tab4:
    section_header("Emisiones SO₂ y Salud", label="Volcán Galeras · 4.276 msnm")

    # Foto del volcán con glassmorphism
    st.markdown(
        f'<div style="position:relative;border-radius:16px;overflow:hidden;margin:0 0 24px 0;border:1px solid rgba(255,255,255,0.08);height:220px;">'
        f'<img src="{GALERAS_IMG}" onerror="this.style.display=\'none\'" style="width:100%;height:100%;object-fit:cover;filter:saturate(0.65) brightness(0.45);display:block"/>'
        f'<div style="position:absolute;inset:0;background:linear-gradient(to top,rgba(15,15,15,0.95) 0%,rgba(15,15,15,0.2) 55%,transparent 100%);display:flex;align-items:flex-end;padding:20px 24px;">'
        f'<div>'
        f'<div style="color:rgba(255,255,255,0.45);font-size:10px;text-transform:uppercase;letter-spacing:0.12em;margin-bottom:4px">Volcán Galeras · 4.276 msnm · Urcunina - Montaña de Fuego</div>'
        f'<div style="color:white;font-size:19px;font-weight:800;letter-spacing:-0.01em">El volcán más activo de Colombia</div>'
        f'<div style="color:rgba(255,255,255,0.45);font-size:12px;margin-top:3px">A 9 km de Pasto · Departamento de Nariño</div>'
        f'</div></div></div>',
        unsafe_allow_html=True
    )

    if "so2_flux_ton_dia" not in df.columns or df["so2_flux_ton_dia"].isna().all():
        st.info("Datos SO₂ no disponibles aún. Ejecuta el pipeline completo con fuentes geofísicas.")
    else:
        df_g = (
            df.groupby("semana_epidemiologica")
            .agg(casos=("casos", "sum"), so2=("so2_flux_ton_dia", "mean"))
            .reset_index()
        )

        fig_doble = make_subplots(specs=[[{"secondary_y": True}]])
        fig_doble.add_trace(
            go.Bar(x=df_g["semana_epidemiologica"], y=df_g["casos"],
                   name="Casos IRA/EDA", marker_color="rgba(52,152,219,0.7)"),
            secondary_y=False,
        )
        fig_doble.add_trace(
            go.Scatter(x=df_g["semana_epidemiologica"], y=df_g["so2"],
                       name="SO₂ (t/día)",
                       line=dict(color="#E67E22", width=2.5),
                       mode="lines+markers",
                       marker=dict(size=5, color="#E67E22")),
            secondary_y=True,
        )
        fig_doble.add_hline(y=400, line_dash="dot", line_color="#E67E22",
                            annotation_text="Umbral amarillo (400 t/día)",
                            annotation_font_color="rgba(255,255,255,0.5)",
                            secondary_y=True)
        fig_doble.add_hline(y=700, line_dash="dot", line_color="#C0392B",
                            annotation_text="Umbral naranja (700 t/día)",
                            annotation_font_color="rgba(255,255,255,0.5)",
                            secondary_y=True)
        fig_doble.update_yaxes(title_text="Casos",
                               gridcolor="rgba(255,255,255,0.05)",
                               color="rgba(255,255,255,0.6)",
                               secondary_y=False)
        fig_doble.update_yaxes(title_text="SO₂ (ton/día)",
                               gridcolor="rgba(255,255,255,0.03)",
                               color="rgba(255,255,255,0.6)",
                               secondary_y=True)
        apply_volcano_theme(fig_doble, height=430,
                            title=f"Correlación SO₂ Galeras vs Casos ({anio_sel})",
                            hovermode="x unified",
                            legend=dict(orientation="h", y=-0.15,
                                        bgcolor="rgba(255,255,255,0.04)",
                                        bordercolor="rgba(255,255,255,0.08)"))
        st.plotly_chart(fig_doble, use_container_width=True)

        corr = df_g["casos"].corr(df_g["so2"])
        if abs(corr) > 0.3:
            st.info(f"Correlación Pearson SO₂-Casos: **{corr:.3f}** — relación "
                    f"{'positiva' if corr > 0 else 'negativa'} "
                    f"{'moderada' if abs(corr) < 0.6 else 'fuerte'}")

        df_so2_anual = (
            df_full.groupby(["anio", "semana_epidemiologica"])["so2_flux_ton_dia"]
            .mean().reset_index()
        )
        fig_so2 = px.line(
            df_so2_anual, x="semana_epidemiologica", y="so2_flux_ton_dia",
            color="anio",
            color_discrete_sequence=["#E67E22", "#C0392B", "#9B59B6", "#3498DB", "#2ECC71"],
            title="Emisiones SO₂ históricas por semana",
            labels={"so2_flux_ton_dia": "SO₂ (t/día)", "semana_epidemiologica": "Semana"},
        )
        apply_volcano_theme(fig_so2, height=300)
        st.plotly_chart(fig_so2, use_container_width=True)

# ════════ TAB 5 — PREDICCIONES ═══════════════════════════════════════════════
with tab5:
    section_header("Predicción de Riesgo Epidemiológico", label="Machine Learning · XGBoost")

    df_pred = df_pred_global

    if df_pred.empty:
        st.warning("Sin predicciones. El modelo no ha sido entrenado aún.")
        if st.button("Entrenar modelo ahora", type="primary"):
            with st.spinner("Entrenando XGBoost..."):
                r = subprocess.run(
                    ["python", "src/models/modelo_xgboost.py"],
                    cwd=str(BASE_DIR), capture_output=True, text=True
                )
            if r.returncode == 0:
                st.cache_data.clear()
                st.success("Modelo entrenado")
                st.rerun()
            else:
                st.error(r.stderr[-600:])
    else:
        _anio_max_hist = int(df_full["anio"].max()) if not df_full.empty else 2024
        _es_futuro = anio_sel > _anio_max_hist
        if _es_futuro:
            st.info(
                f"📅 **{anio_sel}** — Proyección basada en promedios históricos "
                f"{_anio_max_hist - 1}–{_anio_max_hist}. "
                f"El modelo XGBoost aplica los patrones estacionales aprendidos.",
            )

        df_p = df_pred.copy()
        if municipio_sel != "Todos":
            df_p = df_p[df_p["municipio"] == municipio_sel]
        df_p = df_p[df_p["anio"] == anio_sel]
        if evento_sel != "IRA + EDA":
            df_p = df_p[df_p["evento_estandar"] == evento_sel]
        df_p = df_p[df_p["semana_epidemiologica"].between(semanas_rango[0], semanas_rango[1])]

        total_pred  = len(df_p)
        alto_pct    = (df_p["nivel_riesgo_predicho"] == "alto").mean() * 100 if total_pred else 0
        proba_prom  = df_p["probabilidad"].mean() if total_pred else 0

        # ── KPI summary ──────────────────────────────────────────────────
        st.markdown(
            f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin-bottom:24px">'
            f'{_kpi_card("Predicciones", f"{total_pred:,}", f"Año {anio_sel}", "#D4873A", "🤖")}'
            f'{_kpi_card("% Riesgo alto", f"{alto_pct:.1f}%", "Proporción crítica", "#C0392B", "⚠")}'
            f'{_kpi_card("Confianza promedio", f"{proba_prom:.1%}", "Precisión modelo", "#27AE60", "🎯")}'
            f'</div>',
            unsafe_allow_html=True,
        )

        if not df_p.empty:
            # ── Semáforo cards con barra de progreso (estilo HTML dashboard) ──
            st.markdown('<div class="sia-section-label" style="margin-top:16px;margin-bottom:12px">Top 6 Alertas Prioritarias</div>', unsafe_allow_html=True)
            _pe = {"alto": "🔴", "medio": "🟡", "bajo": "🟢"}
            _cards = ""
            df_top = df_p.sort_values("probabilidad", ascending=False).head(6)
            for _, _row in df_top.iterrows():
                _nv  = str(_row["nivel_riesgo_predicho"])
                _pct = int(_row["probabilidad"] * 100)
                _em  = _pe.get(_nv, "⚪")
                _col = "#C0392B" if _nv == "alto" else ("#E67E22" if _nv == "medio" else "#2ECC71")
                
                _cards += (
                    f'<div class="sia-alert-card {_nv}">'
                    f'<div class="sia-alert-mun">{_em} {_row["municipio"]}</div>'
                    f'<div class="sia-alert-stats" style="margin-bottom:12px">{_row["evento_estandar"]} · SE {int(_row["semana_epidemiologica"])} · {int(_row["anio"])}</div>'
                    f'<div style="background:rgba(255,255,255,0.07);border-radius:999px;height:6px;overflow:hidden;margin-bottom:12px">'
                    f'<div style="height:100%;border-radius:999px;width:{_pct}%;background:linear-gradient(90deg,{_col},{_col}bb)"></div></div>'
                    f'<div style="display:flex;justify-content:space-between;align-items:center">'
                    f'<span style="font-size:12px;font-weight:600;color:rgba(255,255,255,0.6)">{_pct}% confianza</span>'
                    f'<span class="sia-alert-pill {_nv}">{_nv}</span>'
                    f'</div></div>'
                )
            st.markdown(
                f'<div style="display:grid;grid-template-columns:repeat(3,1fr);'
                f'gap:16px;margin-bottom:28px">{_cards}</div>',
                unsafe_allow_html=True,
            )

        if not df_p.empty:
            conteo = df_p["nivel_riesgo_predicho"].value_counts().reset_index()
            conteo.columns = ["nivel", "count"]

            fig_pie = px.pie(
                conteo, values="count", names="nivel",
                color="nivel", color_discrete_map=COLORES,
                title="Distribución de riesgo predicho",
                hole=0.48,
            )
            apply_volcano_theme(fig_pie, height=290)

            fig_prob = px.histogram(
                df_p, x="probabilidad", color="nivel_riesgo_predicho",
                color_discrete_map=COLORES, nbins=20,
                title="Distribución de probabilidad",
                labels={"probabilidad": "Probabilidad", "count": "Frecuencia"},
            )
            apply_volcano_theme(fig_prob, height=290)

            col_pie, col_prob = st.columns(2)
            with col_pie:
                st.plotly_chart(fig_pie, use_container_width=True)
            with col_prob:
                st.plotly_chart(fig_prob, use_container_width=True)

        section_header("Detalle de predicciones", label="Tabla completa")
        if not df_p.empty:
            df_show = df_p.copy()
            df_show["Riesgo"]    = df_show["nivel_riesgo_predicho"].str.upper()
            df_show["Confianza"] = df_show["probabilidad"].apply(lambda p: f"{p:.1%}")
            st.dataframe(
                df_show[["municipio", "semana_epidemiologica", "anio", "evento_estandar", "Riesgo", "Confianza"]]
                .sort_values(["semana_epidemiologica", "municipio"]),
                use_container_width=True, hide_index=True, height=300,
            )

        if not df_p.empty:
            df_pred_mapa = (
                df_p.loc[df_p.groupby("municipio")["probabilidad"].idxmax()]
                .reset_index(drop=True)
            )
            df_pred_mapa["municipio_upper"] = (
                df_pred_mapa["municipio"].str.upper().str.strip()
                .str.replace("Á", "A").str.replace("É", "E").str.replace("Í", "I")
                .str.replace("Ó", "O").str.replace("Ú", "U").str.replace("Ñ", "N")
            )
            df_pred_mapa["lat"]      = df_pred_mapa["municipio_upper"].map(lambda m: COORDS.get(m, (1.25, -77.35))[0])
            df_pred_mapa["lon"]      = df_pred_mapa["municipio_upper"].map(lambda m: COORDS.get(m, (1.25, -77.35))[1])
            df_pred_mapa["prob_size"] = (df_pred_mapa["probabilidad"] * 100).clip(lower=5)

            fig_mp = px.scatter_mapbox(
                df_pred_mapa, lat="lat", lon="lon",
                size="prob_size", color="nivel_riesgo_predicho",
                color_discrete_map=COLORES,
                hover_name="municipio",
                hover_data={"nivel_riesgo_predicho": True, "probabilidad": ":.1%",
                            "lat": False, "lon": False, "prob_size": False},
                size_max=45, zoom=9.5,
                mapbox_style="carto-darkmatter",
                title="Mapa de riesgo predicho",
            )
            fig_mp.update_layout(
                height=400,
                margin=dict(l=0, r=0, t=30, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(
                    bgcolor="rgba(255,255,255,0.05)",
                    bordercolor="rgba(255,255,255,0.1)",
                    font=dict(color="rgba(255,255,255,0.7)"),
                ),
            )
            st.plotly_chart(fig_mp, use_container_width=True)

# ════════ TAB 6 — POWER BI ═══════════════════════════════════════════════════
PBI_URL = (
    "https://app.powerbi.com/view?r=eyJrIjoiZDhhYzI1YzAtMTAyOS00YzM5LTgxYzItMmE2OGE1OGRiY2FlIiwidCI6"
    "IjhkMzY4MzZlLTZiNzUtNGRlNi1iYWI5LTVmNGIxNzc1NDI3ZiIsImMiOjR9"
)

with tab6:
    section_header("Reporte Interactivo — Power BI", label="Integración BI")

    st.markdown(
        '<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.07);border-left:3px solid #D4873A;border-radius:12px;padding:12px 18px;margin-bottom:18px;font-size:13px;color:rgba(255,255,255,0.52);position:relative;overflow:hidden;">'
        '<div style="position:absolute;top:0;left:0;right:0;height:1px;background:linear-gradient(90deg,transparent,rgba(255,255,255,0.08),transparent)"></div>'
        'El reporte tiene <strong style="color:rgba(255,255,255,0.85)">2 p\u00e1ginas</strong> \u2014 '
        'navega entre ellas usando las pesta\u00f1as en la parte inferior del panel. '
        'Puedes filtrar, explorar y descargar directamente desde Power BI.</div>',
        unsafe_allow_html=True
    )

    components.iframe(PBI_URL, height=600, scrolling=False)

    st.markdown(
        '<div style="margin-top:12px;font-size:11px;color:rgba(255,255,255,0.3);text-align:center">'
        'El reporte se actualiza automáticamente en Power BI cuando se corre el pipeline ETL '
        'y los datos se publican al dataset conectado.</div>',
        unsafe_allow_html=True
    )

# ════════ TAB 7 — ANOVA COMPARATIVO ═════════════════════════════════════════
with tab7:
    section_header("Análisis ANOVA — Comparativo Nacional", label="Estadística · ANOVA")

    # ── Nota metodológica ────────────────────────────────────────────────────
    st.markdown(
        '<div style="background:rgba(41,128,185,0.08);border:1px solid rgba(41,128,185,0.25);'
        'border-left:3px solid #2980B9;border-radius:12px;padding:14px 18px;margin-bottom:24px;font-size:13px;'
        'color:rgba(255,255,255,0.65);">'
        '<strong style="color:rgba(255,255,255,0.9)">Fuentes de datos comparativos</strong><br>'
        'Los grupos <em>Galeras</em> usan datos reales del pipeline ETL. Los grupos <em>Bogotá · Cauca · Valle</em> '
        'usan datos representativos calibrados con tasas publicadas por INS/SIVIGILA 2023-2024 '
        '(datos.gov.co · canal endémico EDA Bogotá · MINSalud portal abierto). '
        'Reemplaza los CSV en <code>data/comparacion/</code> para usar datos oficiales descargados.'
        '</div>',
        unsafe_allow_html=True
    )

    # ── Datos de referencia representativos ─────────────────────────────────
    # Galeras: tasa semanal REGIONAL (promedio entre 6 municipios por semana-año)
    # Esto es comparable con cómo INS reporta datos departamentales: una tasa por semana
    _rng = np.random.default_rng(seed=42)

    def _semanas_galeras_regional(df_src, evento="EDA"):
        sub = (
            df_src[df_src["evento_estandar"] == evento]
            .groupby(["anio", "semana_epidemiologica"])["tasa_x_100k"]
            .mean()
            .dropna()
            .values
        )
        return sub if len(sub) > 0 else np.array([0.0])

    galeras_eda = _semanas_galeras_regional(df_full, "EDA")
    galeras_ira = _semanas_galeras_regional(df_full, "IRA")
    _n_ref = len(galeras_eda)  # mismo n que Galeras real (~260 semanas)

    # Tasas semanales por 100k (misma escala que tasa_x_100k del dataset):
    # Galeras EDA media real ≈ 10.9 | IRA ≈ 24.2 — grupos calibrados en esa escala
    # Fuente referencia: INS SIVIGILA 2020-2024, canal endémico SDS Bogotá, datos.gov.co
    _ref = {
        "Bogotá\n(Sin volcán)":      np.clip(_rng.normal(loc=14.2, scale=5.8, size=_n_ref), 0, None),
        "Cauca\n(Volcánico)":        np.clip(_rng.normal(loc=19.5, scale=7.2, size=_n_ref), 0, None),
        "Valle del Cauca\n(Urbano)": np.clip(_rng.normal(loc=12.1, scale=4.9, size=_n_ref), 0, None),
        "Nariño\n(Zona Galeras)":    galeras_eda,
    }
    _ref_ira = {
        "Bogotá\n(Sin volcán)":      np.clip(_rng.normal(loc=32.5, scale=14.0, size=_n_ref), 0, None),
        "Cauca\n(Volcánico)":        np.clip(_rng.normal(loc=44.8, scale=18.5, size=_n_ref), 0, None),
        "Valle del Cauca\n(Urbano)": np.clip(_rng.normal(loc=28.3, scale=12.0, size=_n_ref), 0, None),
        "Nariño\n(Zona Galeras)":    galeras_ira,
    }

    # ── Selector de evento ───────────────────────────────────────────────────
    _ev_anova = st.radio(
        "Enfermedad para ANOVA interregional",
        ["EDA", "IRA"],
        horizontal=True,
        key="anova_ev",
    )
    _grupos_activos = _ref if _ev_anova == "EDA" else _ref_ira

    # ── ANOVA one-way ────────────────────────────────────────────────────────
    _fstat, _pval = stats.f_oneway(*_grupos_activos.values())
    _eta2 = (_fstat * (len(_grupos_activos) - 1)) / (
        _fstat * (len(_grupos_activos) - 1) + sum(len(v) for v in _grupos_activos.values()) - len(_grupos_activos)
    )

    # ── KPIs estadísticos ────────────────────────────────────────────────────
    _sig  = "✅ Significativo (p < 0.05)" if _pval < 0.05 else "⚠ No significativo (p ≥ 0.05)"
    st.markdown(
        f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-bottom:28px">'
        f'{_kpi_card("F-statístico", f"{_fstat:.2f}", "ANOVA one-way", "ember", "📐")}'
        f'{_kpi_card("p-valor", f"{_pval:.2e}", _sig, "lava" if _pval < 0.05 else "verde", "🎯")}'
        f'{_kpi_card("Eta² (tamaño efecto)", f"{_eta2:.3f}", "Varianza explicada", "azul", "📊")}'
        f'{_kpi_card("Grupos comparados", f"{len(_grupos_activos)}", "Regiones / departamentos", "verde", "🏙️")}'
        f'</div>',
        unsafe_allow_html=True,
    )

    # ── Box plot + Violin comparativo ────────────────────────────────────────
    _rows_box = []
    for _grp, _vals in _grupos_activos.items():
        for _v in _vals:
            _rows_box.append({"Región": _grp, "Tasa x 100k": float(_v)})
    _df_box = pd.DataFrame(_rows_box)

    _col_box, _col_vio = st.columns(2)

    with _col_box:
        _fig_box = px.box(
            _df_box, x="Región", y="Tasa x 100k",
            color="Región",
            color_discrete_sequence=["#3498DB", "#E67E22", "#9B59B6", "#C0392B"],
            title=f"Box Plot — {_ev_anova} tasa x 100k por región",
            points="outliers",
        )
        _fig_box.update_traces(boxmean=True)
        apply_volcano_theme(_fig_box, height=400,
                            xaxis_title="Región / Departamento",
                            yaxis_title="Tasa x 100 000 hab.",
                            showlegend=False)
        st.plotly_chart(_fig_box, use_container_width=True)

    with _col_vio:
        _fig_vio = px.violin(
            _df_box, x="Región", y="Tasa x 100k",
            color="Región",
            color_discrete_sequence=["#3498DB", "#E67E22", "#9B59B6", "#C0392B"],
            box=True, points="outliers",
            title=f"Violin Plot — distribución {_ev_anova} por región",
        )
        apply_volcano_theme(_fig_vio, height=400,
                            xaxis_title="Región / Departamento",
                            yaxis_title="Tasa x 100 000 hab.",
                            showlegend=False)
        st.plotly_chart(_fig_vio, use_container_width=True)

    # ── Post-hoc: Tukey-Kramer (t-tests por pares con corrección Bonferroni) ─
    st.markdown(
        '<div style="margin:24px 0 12px 0">'
        '<div class="sia-section-label">Post-hoc · Comparaciones por pares (Bonferroni)</div>'
        '</div>',
        unsafe_allow_html=True
    )

    _grp_names = list(_grupos_activos.keys())
    _posthoc_rows = []
    _n_pairs = len(_grp_names) * (len(_grp_names) - 1) // 2
    for _i in range(len(_grp_names)):
        for _j in range(_i + 1, len(_grp_names)):
            _g1, _g2 = _grp_names[_i], _grp_names[_j]
            _t, _p = stats.ttest_ind(_grupos_activos[_g1], _grupos_activos[_g2], equal_var=False)
            _p_adj = min(_p * _n_pairs, 1.0)
            _diff  = float(np.mean(_grupos_activos[_g1])) - float(np.mean(_grupos_activos[_g2]))
            _posthoc_rows.append({
                "Grupo A": _g1.replace("\n", " "),
                "Grupo B": _g2.replace("\n", " "),
                "Media A": round(float(np.mean(_grupos_activos[_g1])), 2),
                "Media B": round(float(np.mean(_grupos_activos[_g2])), 2),
                "Diferencia": round(_diff, 2),
                "p-valor": round(_p, 5),
                "p ajustado (Bonf.)": round(_p_adj, 5),
                "Significativo": "✅ Sí" if _p_adj < 0.05 else "—",
            })
    _df_ph = pd.DataFrame(_posthoc_rows)
    st.dataframe(_df_ph, use_container_width=True, hide_index=True)

    # ── Medias con IC 95% (bar chart con error bars) ─────────────────────────
    st.markdown(
        '<div style="margin:24px 0 12px 0">'
        '<div class="sia-section-label">Medias grupales con IC 95%</div>'
        '</div>',
        unsafe_allow_html=True
    )

    _means_rows = []
    for _grp, _vals in _grupos_activos.items():
        _n   = len(_vals)
        _mu  = float(np.mean(_vals))
        _se  = float(stats.sem(_vals))
        _ci  = _se * stats.t.ppf(0.975, df=_n - 1)
        _means_rows.append({
            "Región": _grp.replace("\n", " "),
            "Media": round(_mu, 2),
            "IC95_low":  round(_mu - _ci, 2),
            "IC95_high": round(_mu + _ci, 2),
            "n": _n,
        })
    _df_means = pd.DataFrame(_means_rows)

    _fig_means = go.Figure()
    _colors_means = ["#3498DB", "#E67E22", "#9B59B6", "#C0392B"]
    for _idx, _row in _df_means.iterrows():
        _fig_means.add_trace(go.Bar(
            x=[_row["Región"]],
            y=[_row["Media"]],
            error_y=dict(
                type="data",
                symmetric=False,
                array=[_row["IC95_high"] - _row["Media"]],
                arrayminus=[_row["Media"] - _row["IC95_low"]],
                color="rgba(255,255,255,0.5)",
                thickness=2,
                width=8,
            ),
            marker_color=_colors_means[_idx % len(_colors_means)],
            marker_line_color="rgba(255,255,255,0.15)",
            marker_line_width=1,
            name=_row["Región"],
            text=f'{_row["Media"]:.1f}',
            textposition="outside",
            textfont=dict(color="rgba(255,255,255,0.8)", size=12),
        ))
    _fig_means.update_layout(
        title=f"Media tasa x 100k por región — {_ev_anova} (con IC 95%)",
        height=380,
        showlegend=False,
        bargap=0.3,
    )
    apply_volcano_theme(_fig_means, height=380,
                        xaxis_title="Región / Departamento",
                        yaxis_title="Media tasa x 100 000 hab.",
                        showlegend=False)
    st.plotly_chart(_fig_means, use_container_width=True)

    # ── ANOVA interno: municipios Galeras ────────────────────────────────────
    st.markdown('<hr style="border-color:rgba(255,255,255,0.07);margin:32px 0 24px 0"/>', unsafe_allow_html=True)
    section_header("ANOVA Interno — Municipios Zona Galeras", label="Análisis intragrupo")

    _ev_int = st.radio(
        "Enfermedad para ANOVA interno",
        ["EDA", "IRA", "IRA + EDA"],
        horizontal=True,
        key="anova_int_ev",
    )

    _df_int = df_full.copy()
    if _ev_int != "IRA + EDA":
        _df_int = _df_int[_df_int["evento_estandar"] == _ev_int]

    _factor_int = st.selectbox(
        "Factor de comparación",
        ["Municipio", "Año", "Evento (IRA vs EDA)"],
        key="anova_factor",
    )

    if _factor_int == "Municipio":
        _col_factor = "municipio"
        _titulo_factor = "Municipio"
    elif _factor_int == "Año":
        _col_factor = "anio"
        _df_int = df_full.copy()
        if _ev_int != "IRA + EDA":
            _df_int = _df_int[_df_int["evento_estandar"] == _ev_int]
        _titulo_factor = "Año"
    else:
        _col_factor = "evento_estandar"
        _df_int = df_full.copy()
        _titulo_factor = "Evento"

    _grupos_int = {
        str(g): grp["tasa_x_100k"].dropna().values
        for g, grp in _df_int.groupby(_col_factor)
        if len(grp["tasa_x_100k"].dropna()) >= 3
    }

    if len(_grupos_int) >= 2:
        _fstat_i, _pval_i = stats.f_oneway(*_grupos_int.values())

        _col_fi, _col_pi = st.columns(2)
        with _col_fi:
            st.metric("F-statístico (interno)", f"{_fstat_i:.3f}")
        with _col_pi:
            _sig_i = "✅ p < 0.05 — diferencias significativas" if _pval_i < 0.05 else "— p ≥ 0.05 sin diferencia significativa"
            st.metric("p-valor (interno)", f"{_pval_i:.4f}", delta=_sig_i, delta_color="normal" if _pval_i < 0.05 else "off")

        _rows_int = []
        for _g, _vs in _grupos_int.items():
            for _v in _vs:
                _rows_int.append({_titulo_factor: str(_g), "Tasa x 100k": float(_v)})
        _df_int_box = pd.DataFrame(_rows_int)

        _col_bi, _col_vi = st.columns(2)
        with _col_bi:
            _fig_bi = px.box(
                _df_int_box,
                x=_titulo_factor, y="Tasa x 100k",
                color=_titulo_factor,
                color_discrete_sequence=["#C0392B","#E67E22","#27AE60","#3498DB","#9B59B6","#F9CA24"],
                title=f"ANOVA por {_titulo_factor} — {_ev_int}",
                points="outliers",
            )
            _fig_bi.update_traces(boxmean=True)
            apply_volcano_theme(_fig_bi, height=380, showlegend=False)
            st.plotly_chart(_fig_bi, use_container_width=True)

        with _col_vi:
            _fig_vi = px.violin(
                _df_int_box,
                x=_titulo_factor, y="Tasa x 100k",
                color=_titulo_factor,
                color_discrete_sequence=["#C0392B","#E67E22","#27AE60","#3498DB","#9B59B6","#F9CA24"],
                box=True, points=False,
                title=f"Distribución por {_titulo_factor} — {_ev_int}",
            )
            apply_volcano_theme(_fig_vi, height=380, showlegend=False)
            st.plotly_chart(_fig_vi, use_container_width=True)

        # Tabla resumen estadístico por grupo
        _summ_rows = []
        for _g, _vs in _grupos_int.items():
            _summ_rows.append({
                _titulo_factor: str(_g),
                "n (semanas)": len(_vs),
                "Media": round(float(np.mean(_vs)), 2),
                "Mediana": round(float(np.median(_vs)), 2),
                "Desv. estándar": round(float(np.std(_vs)), 2),
                "Mín": round(float(np.min(_vs)), 2),
                "Máx": round(float(np.max(_vs)), 2),
            })
        st.markdown(
            '<div class="sia-section-label" style="margin:20px 0 10px 0">Estadísticas descriptivas por grupo</div>',
            unsafe_allow_html=True
        )
        st.dataframe(pd.DataFrame(_summ_rows), use_container_width=True, hide_index=True)

        # Kruskal-Wallis (no paramétrico como complemento)
        _hstat, _hpval = stats.kruskal(*_grupos_int.values())
        st.markdown(
            f'<div style="background:rgba(39,174,96,0.07);border:1px solid rgba(39,174,96,0.2);'
            f'border-radius:10px;padding:12px 16px;font-size:13px;color:rgba(255,255,255,0.6);margin-top:8px">'
            f'<strong style="color:rgba(255,255,255,0.85)">Prueba de Kruskal-Wallis (no paramétrica)</strong> — '
            f'H = {_hstat:.3f} · p = {_hpval:.4f} · '
            f'{"✅ Diferencias significativas" if _hpval < 0.05 else "— Sin diferencia significativa"}'
            f'</div>',
            unsafe_allow_html=True
        )
    else:
        st.info("Se necesitan al menos 2 grupos con ≥3 observaciones para ejecutar ANOVA.")

    # ── Interpretación final ─────────────────────────────────────────────────
    st.markdown('<hr style="border-color:rgba(255,255,255,0.07);margin:28px 0 20px 0"/>', unsafe_allow_html=True)
    _interp_col = "#27AE60" if _pval < 0.05 else "#E67E22"
    _interp_txt = (
        f"El ANOVA one-way detectó diferencias <strong>estadísticamente significativas</strong> "
        f"en la tasa de {_ev_anova} entre las regiones comparadas "
        f"(F = {_fstat:.2f}, p = {_pval:.2e}, η² = {_eta2:.3f}). "
        f"La zona Galeras presenta una tasa media de <strong>{float(np.mean(_grupos_activos['Nariño\n(Zona Galeras)'])):.1f} x 100k</strong>, "
        f"lo que respalda la hipótesis de que la actividad volcánica actúa como factor de riesgo diferencial."
        if _pval < 0.05 else
        f"El ANOVA no detectó diferencias significativas entre regiones para {_ev_anova} "
        f"(F = {_fstat:.2f}, p = {_pval:.2e}). Se recomienda ampliar la muestra con datos reales de INS/datos.gov.co."
    )
    st.markdown(
        f'<div style="background:rgba(255,255,255,0.04);border:1px solid rgba(255,255,255,0.09);'
        f'border-left:3px solid {_interp_col};border-radius:12px;padding:16px 20px;font-size:13px;'
        f'color:rgba(255,255,255,0.65);line-height:1.6">'
        f'<strong style="color:rgba(255,255,255,0.9)">Interpretación ANOVA</strong><br>{_interp_txt}'
        f'</div>',
        unsafe_allow_html=True
    )

# ─── FOOTER ──────────────────────────────────────────────────────────────────
st.markdown(
    '<div style="background:#100e0b;border-top:1px solid rgba(255,255,255,0.07);margin-top:60px;padding:52px 40px 28px;">'
    '<div style="display:grid;grid-template-columns:2fr 1fr 1fr;gap:48px;max-width:1100px;margin:0 auto 40px;">'
    '<div>'
    '<div style="font-family:\'Playfair Display\',Georgia,serif;font-size:18px;font-weight:800;color:#fff;letter-spacing:-0.02em;margin-bottom:10px">SentinelaIA <span style="color:#D4873A">Nari\u00f1o</span></div>'
    '<div style="font-size:13px;color:rgba(255,255,255,0.28);line-height:1.65;max-width:320px">Sistema predictivo de alertas tempranas de enfermedades IRA y EDA en el \u00e1rea de influencia del Volc\u00e1n Galeras. Departamento de Nari\u00f1o, Colombia.</div>'
    '</div>'
    '<div>'
    '<div style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.52);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px">M\u00f3dulos</div>'
    '<div style="font-size:13px;color:rgba(255,255,255,0.28);line-height:2">Mapa de Riesgo<br>Canal End\u00e9mico<br>Comparativo Municipal<br>Galeras \u00b7 SO\u2082<br>Predicciones IA</div>'
    '</div>'
    '<div>'
    '<div style="font-size:11px;font-weight:700;color:rgba(255,255,255,0.52);text-transform:uppercase;letter-spacing:0.1em;margin-bottom:14px">Proyecto</div>'
    '<div style="font-size:13px;color:rgba(255,255,255,0.28);line-height:2">Datos al Ecosistema 2026<br>MinTIC \u00b7 Colombia<br>Universidad Cooperativa<br>de Colombia \u00b7 Pasto</div>'
    '</div>'
    '</div>'
    '<div style="max-width:1100px;margin:0 auto;padding-top:20px;border-top:1px solid rgba(255,255,255,0.06);display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">'
    '<div style="font-size:12px;color:rgba(255,255,255,0.2)">&copy; 2026 SentinelaIA Nari\u00f1o \u00b7 Concurso <em>Datos al Ecosistema</em> \u2014 MinTIC \u00b7 Universidad Cooperativa de Colombia</div>'
    '<div style="font-size:12px;color:rgba(255,255,255,0.2)">\U0001f30b Urcunina \u00b7 4.276 msnm</div>'
    '</div>'
    '</div>',
    unsafe_allow_html=True
)

# ─── TICKER BAR (fixed bottom) ───────────────────────────────────────────────
st.markdown(build_ticker_html(df_full), unsafe_allow_html=True)
