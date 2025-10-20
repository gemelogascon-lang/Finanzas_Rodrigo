# app.py — Finanzas personales (orden por FECHA en Últimos 8)
from __future__ import annotations

import time, math
from datetime import date, timedelta, datetime
import pandas as pd
import streamlit as st

# ==========================
#   CONFIG & THEME
# ==========================
st.set_page_config(page_title="Finanzas", page_icon="💳", layout="wide")

PRIMARY = "#0E7AFE"   # BBVA
PURPLE  = "#7A43F0"   # NU
DARK    = "#2F2F2F"   # GBM
ACCENT  = "#EEF2F8"
GREEN   = "#0A8A4E"
RED     = "#D7263D"
BLACK   = "#0B0B0B"

# --- tap-to-reveal: procesa el query param ?toggle=NU|GBM ---
try:
    qp = st.query_params  # Streamlit >=1.32
except Exception:
    qp = {}

toggle_target = None
if qp and "toggle" in qp:
    v = qp.get("toggle")
    if isinstance(v, (list, tuple)): v = v[0]
    if v in ("NU", "GBM"):
        toggle_target = v

# flags de visibilidad (ocultos por defecto)
for _code in ("NU", "GBM"):
    if f"reveal_{_code}" not in st.session_state:
        st.session_state[f"reveal_{_code}"] = False

if toggle_target:
    st.session_state[f"reveal_{toggle_target}"] = not st.session_state.get(f"reveal_{toggle_target}", False)
    try:
        st.query_params.clear()
    except Exception:
        pass

# ==========================
#   CSS (tarjetas, blur, responsive)
# ==========================
st.markdown(f"""
<style>
:root {{
  --radius: 18px;
  --shadow-1: 0 8px 24px rgba(15, 23, 42, .06);
  --shadow-2: 0 12px 36px rgba(15, 23, 42, .12);
}}
.section-title {{ font-weight:900; font-size:22px; margin:4px 0 14px; }}
.grid-accounts {{
  display:grid; grid-template-columns:repeat(4,1fr); gap:18px;
}}
@media (max-width:1100px) {{ .grid-accounts {{ grid-template-columns:repeat(2,1fr); }} }}
@media (max-width:640px)  {{ .grid-accounts {{ grid-template-columns:1fr; }} }}

/* ---- Tarjeta ---- */
.bank-card {{
  position:relative; border-radius:var(--radius); padding:18px;
  box-shadow:var(--shadow-1); overflow:hidden;
  transition:transform .18s ease, box-shadow .18s ease;
  border:1px solid rgba(16,24,40,.06);
}}
.bank-card:hover {{ transform:translateY(-2px); box-shadow:var(--shadow-2); }}
.theme-blue  {{ --bg1:#F4F8FF; --bg2:#E8F1FF; --accent:{PRIMARY}; }}
.theme-purple{{ --bg1:#F8F3FF; --bg2:#EFE7FF; --accent:{PURPLE};  }}
.theme-dark  {{ --bg1:#F7F8FA; --bg2:#ECEFF3; --accent:{DARK};    }}
.bank-card {{ background:linear-gradient(165deg,var(--bg1) 0%,var(--bg2) 100%); }}
.bank-card::after {{
  content:""; position:absolute; inset:0;
  background:
    radial-gradient(18px 18px at 24px 24px, rgba(0,0,0,.04), transparent 60%),
    radial-gradient(18px 18px at 72px 12px, rgba(0,0,0,.03), transparent 60%);
  mix-blend-mode:multiply; opacity:.35; pointer-events:none;
}}
.badge-type {{
  position:absolute; top:10px; right:10px; font-size:11px; font-weight:800;
  letter-spacing:.3px; color:#fff; padding:6px 10px; border-radius:999px;
  box-shadow:0 6px 14px rgba(0,0,0,.15);
  background:linear-gradient(135deg, var(--accent), color-mix(in oklab, var(--accent) 60%, white 40%));
}}
.brand {{ display:flex; align-items:center; gap:12px; margin-top:6px; }}
.brand .mono {{
  width:44px; height:44px; border-radius:12px; display:flex; align-items:center; justify-content:center;
  font-weight:900; background:#fff; border:1px solid color-mix(in oklab, var(--accent) 25%, transparent);
  color:#111; letter-spacing:.3px;
}}
.brand h4 {{ margin:0; font-size:15px; color:#0b0b0b; }}
.amount {{ font-weight:900; font-size:28px; margin:6px 0 4px 0; color:var(--accent); }}
.helper {{ color:#667085; font-size:12px; line-height:1.2; }}

/* tap sobre el monto (link invisible que conserva estilos) */
.tap {{ color:inherit; text-decoration:none; }}
.tap:hover {{ opacity:.92; cursor:pointer; }}

/* oculta saldo */
.blur {{ filter: blur(9px); }}

.progress-ring {{
  width:110px; height:110px; border-radius:50%;
  display:flex; align-items:center; justify-content:center;
  position:relative; box-shadow:var(--shadow-1);
}}
.progress-ring .inner {{
  width:86px; height:86px; border-radius:50%; background:#fff;
  display:flex; align-items:center; justify-content:center;
  font-weight:800; font-size:18px;
}}

.confirm-box {{
  border:1px solid #ffd3d3; background:#fff6f6; padding:10px;
  border-radius:12px; margin:8px 0;
}}

.row-ultima {{
  padding:10px 12px; border-radius:12px; border:1px solid #E8ECF4; margin-bottom:8px;
  background: #fff;
}}
.row-ultima:hover {{ background: #FAFBFE; }}

.badge-tipo {{
  font-size:11px; font-weight:800; letter-spacing:.3px; padding:4px 8px; border-radius:999px;
  border:1px solid #E0E7F0; background:#F8FAFD;
}}

.text-green {{ color:{GREEN}; }}
.text-red   {{ color:{RED};   }}
.text-black {{ color:{BLACK}; }}

.bottom-nav {{
  position:fixed; bottom:10px; left:50%; transform:translateX(-50%);
  background:#fff; border:1px solid {ACCENT}; border-radius:16px;
  box-shadow:var(--shadow-1); display:flex; gap:14px; padding:10px 14px; z-index:9999;
}}
.bottom-nav button {{
  background:#fff; border:1px solid {ACCENT}; border-radius:10px;
  padding:8px 10px; font-size:14px; cursor:pointer;
}}
</style>
""", unsafe_allow_html=True)

# ==========================
#   GOOGLE SHEETS
# ==========================
import gspread
from google.oauth2.service_account import Credentials
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from gspread.exceptions import APIError

# Validación temprana de secrets
if "SHEET_ID" not in st.secrets:
    st.error("Falta `SHEET_ID` en st.secrets.")
    st.stop()
if "gcp_service_account" not in st.secrets:
    st.error("Faltan credenciales `gcp_service_account` en st.secrets.")
    st.stop()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]
SHEET_ID = st.secrets["SHEET_ID"]
SVC = dict(st.secrets["gcp_service_account"])

@st.cache_resource(show_spinner=False)
def get_client():
    creds = Credentials.from_service_account_info(SVC, scopes=SCOPES)
    return gspread.authorize(creds)

@st.cache_resource(show_spinner=False)
def open_sheet(max_retries: int = 4, base_sleep: float = 0.8):
    """Abre el Spreadsheet con reintentos y mensajes claros de error."""
    last_exc = None
    for i in range(max_retries):
        try:
            return get_client().open_by_key(SHEET_ID)
        except APIError as e:
            last_exc = e
            # backoff exponencial pequeño
            time.sleep(base_sleep * (2 ** i) + 0.05 * (i + 1))
        except Exception as e:
            last_exc = e
            time.sleep(base_sleep * (2 ** i) + 0.05 * (i + 1))
    # Si llegamos aquí, no se pudo abrir
    st.error(
        "No pude abrir tu Google Sheet.\n\n"
        "Verifica lo siguiente:\n"
        "• **SHEET_ID** correcto (la parte entre `/d/` y `/edit` en la URL).\n"
        "• El **Service Account** tiene acceso al archivo (compártelo con el email del service account con permiso de Editor).\n"
        "• Que no haya un bloqueo temporal de la API (intenta nuevamente).\n"
    )
    # Mostrar excepción para depurar localmente
    with st.expander("Detalles técnicos (para depurar)"):
        st.exception(last_exc)
    st.stop()

def ensure_worksheet(sh, title, headers):
    try:
        ws = sh.worksheet(title)
        if not ws.row_values(1):
            ws.append_row(headers)
    except gspread.WorksheetNotFound:
        ws = sh.add_worksheet(title=title, rows=2000, cols=max(20, len(headers)))
        ws.append_row(headers)
    return ws

def _fallback_df(ws):
    vals = ws.get_all_values()
    if not vals:
        return pd.DataFrame()
    if len(vals) == 1:
        return pd.DataFrame(columns=[c.strip() for c in vals[0]])
    headers = [str(c).strip() for c in vals[0]]
    rows = vals[1:]
    df = pd.DataFrame(rows, columns=headers)
    return df

def get_df(ws, dtypes=None, retries=3, backoff=1.2):
    last_exc = None
    for i in range(retries):
        try:
            df = get_as_dataframe(ws, evaluate_formulas=False, dtype=None, headers=True)
            break
        except APIError as e:
            last_exc = e
            time.sleep(backoff * (i+1))
        except Exception as e:
            last_exc = e
            time.sleep(backoff * (i+1))
    else:
        try:
            df = _fallback_df(ws)
        except Exception as e:
            st.error("No pude leer la hoja de cálculo. Revisa permisos y estructura.")
            st.exception(e)
            df = pd.DataFrame()

    if df is None:
        df = pd.DataFrame()
    df = df.dropna(how="all")
    if not df.empty:
        df.columns = [str(c).strip() for c in df.columns]

    if dtypes and not df.empty:
        for c, typ in dtypes.items():
            if c in df.columns:
                try:
                    if typ == "float":
                        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)
                    elif typ == "int":
                        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype(int)
                    elif typ == "date":
                        df[c] = pd.to_datetime(df[c], errors="coerce").dt.date
                    else:
                        df[c] = df[c].astype(str)
                except:
                    pass
    return df.reset_index(drop=True)

def write_df_safe(ws, df, max_retries=5, base_sleep=0.8):
    """Escribe el DataFrame con reintentos exponenciales si hay APIError."""
    attempt = 0
    while True:
        try:
            if df is None:
                return
            if df.empty:
                headers = ws.row_values(1)
                ws.clear()
                if headers:
                    ws.append_row(headers)
                return
            ws.clear()
            set_with_dataframe(ws, df, include_index=False,
                               include_column_header=True, resize=True)
            return
        except APIError:
            attempt += 1
            if attempt >= max_retries:
                raise
            sleep_s = base_sleep * (2 ** (attempt - 1)) + (0.05 * attempt)
            time.sleep(sleep_s)

# Conexión a Sheets
with st.status("Conectando con Sheets…", expanded=False) as s:
    sh    = open_sheet()
    wsCfg = ensure_worksheet(sh, "Config",    ["clave","valor"])
    wsG   = ensure_worksheet(sh, "Gastos",    ["ts","fecha","cuenta","monto","categoria","nota"])
    wsT   = ensure_worksheet(sh, "Traspasos", ["ts","fecha","cuenta_emisora","cuenta_receptora","monto","comentario"])
    wsI   = ensure_worksheet(sh, "Ingresos",  ["ts","fecha","cuenta","monto","categoria","nota"])
    s.update(label="Conectado ✅", state="complete")

@st.cache_data(ttl=2.0)
def read_tables_cached():
    cfg_       = get_df(wsCfg)
    gastos_    = get_df(wsG, dtypes={"monto":"float"})
    traspasos_ = get_df(wsT, dtypes={"monto":"float"})
    ingresos_  = get_df(wsI, dtypes={"monto":"float"})
    return cfg_, gastos_, traspasos_, ingresos_

cfg, gastos, traspasos, ingresos = read_tables_cached()

def ensure_ts(df: pd.DataFrame):
    if df is None or df.empty: return df, False
    changed = False
    if "ts" not in df.columns:
        df["ts"] = pd.Series([None]*len(df)); changed = True
    df["ts"] = pd.to_numeric(df["ts"], errors="coerce")
    base = int(time.time()*1000)
    for i,v in df["ts"].items():
        if pd.isna(v) or v <= 0:
            df.at[i,"ts"] = base + i; changed = True
    df["ts"] = df["ts"].astype("int64")
    return df, changed

gastos, g_ch     = ensure_ts(gastos)
traspasos, t_ch  = ensure_ts(traspasos)
ingresos, i_ch   = ensure_ts(ingresos)
if g_ch: write_df_safe(wsG, gastos)
if t_ch: write_df_safe(wsT, traspasos)
if i_ch: write_df_safe(wsI, ingresos)

def cfg_get(k, default=None):
    if cfg.empty: return default
    r = cfg.loc[cfg["clave"]==k]
    return r["valor"].iloc[0] if not r.empty else default

def cfg_set(k, v):
    global cfg
    if cfg.empty:
        cfg = pd.DataFrame({"clave":[k], "valor":[v]})
    else:
        if k in cfg["clave"].values: cfg.loc[cfg["clave"]==k, "valor"]=v
        else: cfg = pd.concat([cfg, pd.DataFrame({"clave":[k], "valor":[v]})], ignore_index=True)

def cuentas(): return ["BBVA Concentradora","BBVA Credito","NU","GBM"]
def saldo_key(cta): return f"saldo_{cta}"

def get_saldos():
    d = {}
    for c in cuentas():
        try: d[c] = float(cfg_get(saldo_key(c), "0"))
        except: d[c] = 0.0
    return d

def set_saldo(cta, val): cfg_set(saldo_key(cta), str(float(val)))
def set_all_saldos(s): 
    for c,v in s.items(): set_saldo(c, v)

# Defaults de objetivos
if cfg_get("objetivo_semana") is None:        cfg_set("objetivo_semana","1500")
if cfg_get("objetivo_ahorro_mes") is None:    cfg_set("objetivo_ahorro_mes","8500")

# ==========================
#   UI: Refrescar
# ==========================
c1, _ = st.columns([1,8])
with c1:
    if st.button("🔄 Actualizar"):
        st.cache_resource.clear(); st.cache_data.clear(); st.rerun()

# ==========================
#   TARJETAS DE SALDO (NU/GBM con tap-to-reveal)
# ==========================
saldos = get_saldos()

def initials_from(name: str):
    parts = name.replace("BBVA","").strip().split()
    if not parts: return name[:2].upper()
    if len(parts)==1: return parts[0][:2].upper()
    return (parts[0][0]+parts[1][0]).upper()

def is_credit_account(nombre:str)->bool: return nombre=="BBVA Credito"

def card_cuenta_pro(nombre: str, theme: str, sensitive: bool=False):
    val = saldos.get(nombre, 0.0)
    if is_credit_account(nombre):
        if val < 0:   titulo = f"Debe: ${abs(val):,.2f}"
        elif val > 0: titulo = f"A favor: ${val:,.2f}"
        else:         titulo = "Liquidada: $0.00"
        badge_txt = "CRÉDITO"
    else:
        titulo = f"${val:,.2f}"
        badge_txt = "CUENTA"

    initials = initials_from(nombre)
    code = "NU" if nombre=="NU" else ("GBM" if nombre=="GBM" else None)
    reveal_flag = True
    if sensitive and code:
        reveal_flag = bool(st.session_state.get(f"reveal_{code}", False))

    if sensitive and code:
        amount_inner = titulo if reveal_flag else f'<span class="blur">{titulo}</span>'
        amount_html = f'<a class="tap" href="?toggle={code}#card_{code}">{amount_inner}</a>'
    else:
        amount_html = titulo

    anchor = f'id="card_{code}"' if code else ""
    st.markdown(f"""
    <div class="bank-card theme-{theme}" {anchor}>
      <div class="badge-type">{badge_txt}</div>
      <div class="brand">
        <div class="mono">{initials}</div>
        <h4>{nombre}</h4>
      </div>
      <div class="amount">{amount_html}</div>
      <div class="helper">Saldo actualizado desde Google Sheets</div>
    </div>
    """, unsafe_allow_html=True)

st.markdown('<div class="section-title">💰 Saldos de cuentas</div>', unsafe_allow_html=True)
st.markdown('<div class="grid-accounts">', unsafe_allow_html=True)
c1,c2,c3,c4 = st.columns(4, gap="large")
with c1: card_cuenta_pro("BBVA Concentradora","blue",  sensitive=False)
with c2: card_cuenta_pro("BBVA Credito",      "blue",  sensitive=False)
with c3: card_cuenta_pro("NU",                "purple",sensitive=True)
with c4: card_cuenta_pro("GBM",               "dark",  sensitive=True)
st.markdown('</div>', unsafe_allow_html=True)

st.divider()

# ==========================
#   OBJETIVO SEMANAL (izq) + AHORRO MENSUAL (der)
# ==========================
try: objetivo = float(cfg_get("objetivo_semana","1500"))
except: objetivo = 1500.0

try: objetivo_mes = float(cfg_get("objetivo_ahorro_mes","8500"))
except: objetivo_mes = 8500.0

# ---- Semana actual
hoy = date.today()
inicio_sem = hoy - timedelta(days=hoy.weekday())
fin_sem = inicio_sem + timedelta(days=6)

g_sem = gastos.copy()
if not g_sem.empty:
    g_sem["fecha"] = pd.to_datetime(g_sem["fecha"], errors="coerce").dt.date
    g_sem = g_sem[(g_sem["fecha"]>=inicio_sem) & (g_sem["fecha"]<=fin_sem)]
total_sem = float(g_sem["monto"].sum()) if not g_sem.empty else 0.0
restante_sem = max(0.0, objetivo-total_sem)
pct_sem = 0.0 if objetivo<=0 else max(0.0, min(1.0, total_sem/objetivo))
angulo_sem = int(360*pct_sem)

# ---- Mes actual (cambio neto en NU)
inicio_mes = date(hoy.year, hoy.month, 1)
fin_mes = hoy

def _delta_mes_nu():
    total = 0.0
    # Gastos desde NU (negativo)
    if not gastos.empty:
        g = gastos.copy()
        g["fecha"] = pd.to_datetime(g["fecha"], errors="coerce").dt.date
        g = g[(g["fecha"]>=inicio_mes) & (g["fecha"]<=fin_mes) & (g["cuenta"]=="NU")]
        total += -float(g["monto"].sum()) if not g.empty else 0.0
    # Traspasos enviados desde NU (negativo)
    if not traspasos.empty:
        te = traspasos.copy()
        te["fecha"] = pd.to_datetime(te["fecha"], errors="coerce").dt.date
        te = te[(te["fecha"]>=inicio_mes) & (te["fecha"]<=fin_mes) & (te["cuenta_emisora"]=="NU")]
        total += -float(te["monto"].sum()) if not te.empty else 0.0
        # Traspasos recibidos en NU (positivo)
        tr = traspasos.copy()
        tr["fecha"] = pd.to_datetime(tr["fecha"], errors="coerce").dt.date
        tr = tr[(tr["fecha"]>=inicio_mes) & (tr["fecha"]<=fin_mes) & (tr["cuenta_receptora"]=="NU")]
        total += +float(tr["monto"].sum()) if not tr.empty else 0.0
    # Ingresos a NU (positivo)
    if not ingresos.empty:
        inc = ingresos.copy()
        inc["fecha"] = pd.to_datetime(inc["fecha"], errors="coerce").dt.date
        inc = inc[(inc["fecha"]>=inicio_mes) & (inc["fecha"]<=fin_mes) & (inc["cuenta"]=="NU")]
        total += +float(inc["monto"].sum()) if not inc.empty else 0.0
    return total

avance_mes = _delta_mes_nu()  # puede ser negativo
faltante_mes_raw = objetivo_mes - avance_mes
if faltante_mes_raw >= 0:
    faltante_mes_txt = f"Faltante: ${faltante_mes_raw:,.2f}"
else:
    faltante_mes_txt = f"Excedente: ${abs(faltante_mes_raw):,.2f}"
pct_mes = 0.0 if objetivo_mes<=0 else max(0.0, min(1.0, avance_mes/objetivo_mes))
angulo_mes = int(360*pct_mes)

# ---- UI lado a lado
colL, colR = st.columns(2, gap="large")

with colL:
    st.markdown('<div class="section-title">🎯 Objetivo semanal de gasto</div>', unsafe_allow_html=True)
    la, lb = st.columns([1,3])
    with la:
        st.markdown(f"""
        <div class="progress-ring" style="background:conic-gradient({PRIMARY} 0deg, {PRIMARY} {angulo_sem}deg, #E5E9F2 {angulo_sem}deg 360deg);">
          <div class="inner">{int(pct_sem*100)}%</div>
        </div>
        """, unsafe_allow_html=True)
    with lb:
        st.subheader(f"${total_sem:,.2f} / ${objetivo:,.2f}")
        st.caption(f"Semana: {inicio_sem.strftime('%d %b')} – {fin_sem.strftime('%d %b')}")
        st.caption(f"Restante: ${restante_sem:,.2f}")

with colR:
    st.markdown('<div class="section-title">💾 Objetivo de ahorro mensual (NU)</div>', unsafe_allow_html=True)
    ra, rb = st.columns([1,3])
    with ra:
        st.markdown(f"""
        <div class="progress-ring" style="background:conic-gradient({GREEN} 0deg, {GREEN} {angulo_mes}deg, #E5E9F2 {angulo_mes}deg 360deg);">
          <div class="inner">{int(pct_mes*100)}%</div>
        </div>
        """, unsafe_allow_html=True)
    with rb:
        st.subheader(f"${avance_mes:,.2f} / ${objetivo_mes:,.2f}")
        st.caption(f"Mes: {inicio_mes.strftime('%d %b')} – {fin_mes.strftime('%d %b')}")
        st.caption(f"{faltante_mes_txt}")

st.divider()

# ==========================
#   NUEVO MOVIMIENTO
# ==========================
st.markdown('<div class="section-title">➕ Nuevo movimiento</div>', unsafe_allow_html=True)
tg, tt, ti = st.tabs(["Gasto","Traspaso","Ingresos"])

def now_ts(): return int(time.time()*1000)

def registrar_gasto(fecha, cuenta, monto, categoria, nota):
    global gastos, cfg
    row = pd.DataFrame([{
        "ts": now_ts(), "fecha": fecha, "cuenta": cuenta,
        "monto": float(monto), "categoria": categoria, "nota": nota
    }])
    gastos = pd.concat([gastos, row], ignore_index=True)
    s = get_saldos(); s[cuenta] = s.get(cuenta,0.0) - float(monto); set_all_saldos(s)
    write_df_safe(wsG, gastos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()

def registrar_traspaso(fecha, emisora, receptora, monto, comentario):
    global traspasos, cfg
    row = pd.DataFrame([{
        "ts": now_ts(), "fecha": fecha, "cuenta_emisora": emisora,
        "cuenta_receptora": receptora, "monto": float(monto), "comentario": comentario
    }])
    traspasos = pd.concat([traspasos, row], ignore_index=True)
    s = get_saldos()
    s[emisora]   = s.get(emisora,0.0) - float(monto)
    s[receptora] = s.get(receptora,0.0) + float(monto)
    set_all_saldos(s)
    write_df_safe(wsT, traspasos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()

def registrar_ingreso(fecha, cuenta, monto, categoria, nota):
    global ingresos, cfg
    row = pd.DataFrame([{
        "ts": now_ts(), "fecha": fecha, "cuenta": cuenta,
        "monto": float(monto), "categoria": categoria, "nota": nota
    }])
    ingresos = pd.concat([ingresos, row], ignore_index=True)
    s = get_saldos(); s[cuenta] = s.get(cuenta,0.0) + float(monto); set_all_saldos(s)
    write_df_safe(wsI, ingresos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()

with tg:
    with st.form("form_gasto", clear_on_submit=True):
        a,b,c = st.columns(3)
        with a: fecha_g = st.date_input("Fecha", value=date.today())
        with b: cuenta_g = st.selectbox("Cuenta", cuentas())
        with c: monto_g = st.number_input("Monto", min_value=0.0, step=50.0)
        categoria_g = st.selectbox("Categoría", ["Comida","Gasolina","Ocio","Servicios","Otro"])
        nota_g = st.text_input("Nota","")
        if st.form_submit_button("Registrar gasto"):
            if monto_g <= 0: st.error("El monto debe ser mayor a 0.")
            else:
                registrar_gasto(fecha_g, cuenta_g, monto_g, categoria_g, nota_g)
                st.success("✅ Gasto registrado."); st.rerun()

with tt:
    with st.form("form_traspaso", clear_on_submit=True):
        a,b,c = st.columns(3)
        with a: fecha_t = st.date_input("Fecha", value=date.today())
        with b: emisora  = st.selectbox("Cuenta emisora", cuentas())
        with c: receptora= st.selectbox("Cuenta receptora", cuentas(), index=1)
        monto_t = st.number_input("Monto", min_value=0.0, step=50.0)
        comentario_t = st.selectbox("Comentario", ["Inversión","Ahorro","Agregar fondos","Otro"])
        saldo_emisora = get_saldos().get(emisora, 0.0)
        if st.form_submit_button("Registrar traspaso"):
            if monto_t <= 0:
                st.error("El monto debe ser mayor a 0.")
            elif emisora == receptora:
                st.error("La emisora y receptora deben ser distintas.")
            elif monto_t > saldo_emisora:
                st.error("No hay fondos suficientes en la cuenta para completar el traspaso.")
            else:
                registrar_traspaso(fecha_t, emisora, receptora, monto_t, comentario_t)
                st.success("✅ Traspaso registrado."); st.rerun()

with ti:
    with st.form("form_ingreso", clear_on_submit=True):
        a,b,c = st.columns(3)
        with a: fecha_i = st.date_input("Fecha", value=date.today())
        with b: cuenta_i = st.selectbox("Cuenta destino", cuentas())
        with c: monto_i  = st.number_input("Monto", min_value=0.0, step=100.0)
        categoria_i = st.selectbox("Categoría", ["Semana","Nómina","Intereses","Dividendos","Otro"])
        nota_i = st.text_input("Nota","")
        if st.form_submit_button("Registrar ingreso"):
            if monto_i <= 0:
                st.error("El monto debe ser mayor a 0.")
            else:
                registrar_ingreso(fecha_i, cuenta_i, monto_i, categoria_i, nota_i)
                st.success("✅ Ingreso registrado."); st.rerun()

st.divider()

# ==========================
#   ÚLTIMOS MOVIMIENTOS — UNIFICADO (8 más recientes por FECHA)
# ==========================
st.markdown('<div class="section-title">🕒 Últimos movimientos (8 más recientes)</div>', unsafe_allow_html=True)

if "confirm_del" not in st.session_state:
    st.session_state.confirm_del = None

def pedir_confirm(tipo, ts_int): st.session_state.confirm_del = {"tipo":tipo, "ts":ts_int}
def clear_confirm(): st.session_state.confirm_del = None

def eliminar_gasto(ts_id:int):
    global gastos, cfg
    row = gastos.loc[gastos["ts"]==ts_id]
    if row.empty: return False
    r = row.iloc[0]
    cta = r["cuenta"]; mon = float(r["monto"])
    s = get_saldos(); s[cta] = s.get(cta,0.0) + mon; set_all_saldos(s)
    gastos = gastos[gastos["ts"]!=ts_id].reset_index(drop=True)
    write_df_safe(wsG, gastos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()
    return True

def eliminar_traspaso(ts_id:int):
    global traspasos, cfg
    row = traspasos.loc[traspasos["ts"]==ts_id]
    if row.empty: return False
    r = row.iloc[0]
    emi, rec, mon = r["cuenta_emisora"], r["cuenta_receptora"], float(r["monto"])
    s = get_saldos()
    s[emi] = s.get(emi,0.0) + mon
    s[rec] = s.get(rec,0.0) - mon
    set_all_saldos(s)
    traspasos = traspasos[traspasos["ts"]!=ts_id].reset_index(drop=True)
    write_df_safe(wsT, traspasos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()
    return True

def eliminar_ingreso(ts_id:int):
    global ingresos, cfg
    row = ingresos.loc[ingresos["ts"]==ts_id]
    if row.empty: return False
    r = row.iloc[0]
    cta = r["cuenta"]; mon = float(r["monto"])
    s = get_saldos(); s[cta] = s.get(cta,0.0) - mon; set_all_saldos(s)
    ingresos = ingresos[ingresos["ts"]!=ts_id].reset_index(drop=True)
    write_df_safe(wsI, ingresos); write_df_safe(wsCfg, cfg)
    st.cache_data.clear()
    return True

def unified_last8():
    u = []
    if not gastos.empty:
        g = gastos.copy()
        g["ts"] = pd.to_numeric(g["ts"], errors="coerce")
        g["fecha_dt"] = pd.to_datetime(g["fecha"], errors="coerce")
        for _, r in g.iterrows():
            u.append({
                "ts": int(r.get("ts", 0)),
                "fecha_dt": r.get("fecha_dt"),
                "tipo": "Gasto",
                "texto": f"{r.get('cuenta','')} · {r.get('categoria','')}",
                "detalle": (r.get("nota") or ""),
                "monto": float(pd.to_numeric(r.get("monto"), errors="coerce") or 0),
            })
    if not traspasos.empty:
        t = traspasos.copy()
        t["ts"] = pd.to_numeric(t["ts"], errors="coerce")
        t["fecha_dt"] = pd.to_datetime(t["fecha"], errors="coerce")
        for _, r in t.iterrows():
            u.append({
                "ts": int(r.get("ts", 0)),
                "fecha_dt": r.get("fecha_dt"),
                "tipo": "Traspaso",
                "texto": f"{r.get('cuenta_emisora','')} → {r.get('cuenta_receptora','')}",
                "detalle": (r.get("comentario") or ""),
                "monto": float(pd.to_numeric(r.get("monto"), errors="coerce") or 0),
            })
    if not ingresos.empty:
        i = ingresos.copy()
        i["ts"] = pd.to_numeric(i["ts"], errors="coerce")
        i["fecha_dt"] = pd.to_datetime(i["fecha"], errors="coerce")
        for _, r in i.iterrows():
            u.append({
                "ts": int(r.get("ts", 0)),
                "fecha_dt": r.get("fecha_dt"),
                "tipo": "Ingreso",
                "texto": f"{r.get('cuenta','')} · {r.get('categoria','')}",
                "detalle": (r.get("nota") or ""),
                "monto": float(pd.to_numeric(r.get("monto"), errors="coerce") or 0),
            })
    if not u:
        return []
    for x in u:
        f = x.get("fecha_dt")
        if pd.isna(f):
            x["fecha_dt"] = pd.Timestamp.min
    u = [x for x in u if x["ts"]>0]
    u.sort(key=lambda x: (x["fecha_dt"], x["ts"]), reverse=True)
    return u[:8]

lista8 = unified_last8()

def color_for(tipo:str)->str:
    if tipo=="Ingreso":  return "text-green"
    if tipo=="Gasto":    return "text-red"
    return "text-black"  # Traspaso

for idx, item in enumerate(lista8):
    tipo = item["tipo"]; ts_id = item["ts"]
    fdt  = item["fecha_dt"]
    fecha_str = "-" if pd.isna(fdt) else pd.to_datetime(fdt).strftime("%d %b %Y")
    texto  = item["texto"]
    detalle= item["detalle"]
    monto  = item["monto"]

    col = color_for(tipo)
    cont = st.container()
    with cont:
        st.markdown(f"""
        <div class="row-ultima">
          <div style="display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap;">
            <div style="display:flex; align-items:center; gap:10px;">
              <span class="badge-tipo {col}">{tipo}</span>
              <strong>{fecha_str}</strong>
              <span>· {texto}</span>
            </div>
            <div style="display:flex; align-items:center; gap:10px;">
              <span class="{col}" style="font-weight:800;">${monto:,.2f}</span>
            </div>
          </div>
          <div style="margin-top:6px; color:#667085;">{detalle}</div>
        """, unsafe_allow_html=True)

        c1, c2, c3 = st.columns([0.18, 0.18, 0.64])
        if c1.button("🗑️ Eliminar", key=f"del_unif_{tipo}_{ts_id}"):
            pedir_confirm(tipo, ts_id)

        if st.session_state.confirm_del and st.session_state.confirm_del.get("ts")==ts_id and st.session_state.confirm_del.get("tipo")==tipo:
            with c3:
                st.markdown('<div class="confirm-box">', unsafe_allow_html=True)
                st.write(f"¿Seguro que quieres eliminar este {tipo.lower()}?")
                cc1, cc2 = st.columns(2)
                if cc1.button("Sí, eliminar", key=f"yes_unif_{tipo}_{ts_id}"):
                    ok=False
                    if tipo=="Gasto": ok = eliminar_gasto(ts_id)
                    elif tipo=="Traspaso": ok = eliminar_traspaso(ts_id)
                    elif tipo=="Ingreso": ok = eliminar_ingreso(ts_id)
                    clear_confirm()
                    st.success(f"{tipo} eliminado." if ok else "No se encontró el registro.")
                    st.rerun()
                if cc2.button("No, cancelar", key=f"no_unif_{tipo}_{ts_id}"):
                    clear_confirm()
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)

st.divider()

# ==========================
#   DETALLE POR CUENTA
# ==========================
st.markdown('<div class="section-title">📊 Detalle por cuenta</div>', unsafe_allow_html=True)
rango = st.radio("Rango", ["7 días","30 días"], horizontal=True)
dias = 7 if rango=="7 días" else 30
desde = date.today() - timedelta(days=dias)

from plotly import graph_objects as go

# AgGrid opcional
try:
    from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
    AG_OK = True
except Exception:
    AG_OK = False

def detalle(nombre):
    st.subheader(nombre)

    # --- Filtro por cuenta y rango, manteniendo ts para ordenar secundarios ---
    g = gastos.copy()
    if not g.empty:
        g["ts"]     = pd.to_numeric(g["ts"], errors="coerce").astype("Int64")
        g["fecha_dt"]= pd.to_datetime(g["fecha"], errors="coerce")
        g = g[(g["fecha_dt"].dt.date>=desde)&(g["cuenta"]==nombre)]

    te = traspasos.copy()
    if not te.empty:
        te["ts"]     = pd.to_numeric(te["ts"], errors="coerce").astype("Int64")
        te["fecha_dt"]= pd.to_datetime(te["fecha"], errors="coerce")
        te = te[(te["fecha_dt"].dt.date>=desde)&(te["cuenta_emisora"]==nombre)]

    tr = traspasos.copy()
    if not tr.empty:
        tr["ts"]     = pd.to_numeric(tr["ts"], errors="coerce").astype("Int64")
        tr["fecha_dt"]= pd.to_datetime(tr["fecha"], errors="coerce")
        tr = tr[(tr["fecha_dt"].dt.date>=desde)&(tr["cuenta_receptora"]==nombre)]

    inc = ingresos.copy()
    if not inc.empty:
        inc["ts"]     = pd.to_numeric(inc["ts"], errors="coerce").astype("Int64")
        inc["fecha_dt"]= pd.to_datetime(inc["fecha"], errors="coerce")
        inc = inc[(inc["fecha_dt"].dt.date>=desde)&(inc["cuenta"]==nombre)]

    # --- NUEVA TABLA ÚNICA: últimos 7 por fecha desc (y ts) ---
    cols = ["fecha","tipo","monto","detalle"]
    df_u = pd.DataFrame(columns=cols)

    if not g.empty:
        x = pd.DataFrame({
            "fecha":  g["fecha_dt"].dt.date,
            "tipo":   "Gasto",
            "monto":  pd.to_numeric(g["monto"], errors="coerce").astype(float),
            "detalle": g["categoria"].fillna("").astype(str) + g["nota"].fillna("").map(lambda n: f" — {n}" if str(n).strip() else "")
        })
        x["ts"] = g["ts"]
        df_u = pd.concat([df_u, x], ignore_index=True)

    if not te.empty:
        x = pd.DataFrame({
            "fecha":  te["fecha_dt"].dt.date,
            "tipo":   "Traspaso enviado",
            "monto":  pd.to_numeric(te["monto"], errors="coerce").astype(float),
            "detalle": "→ " + te["cuenta_receptora"].astype(str) + te["comentario"].fillna("").map(lambda c: f" ({c})" if str(c).strip() else "")
        })
        x["ts"] = te["ts"]
        df_u = pd.concat([df_u, x], ignore_index=True)

    if not tr.empty:
        x = pd.DataFrame({
            "fecha":  tr["fecha_dt"].dt.date,
            "tipo":   "Traspaso recibido",
            "monto":  pd.to_numeric(tr["monto"], errors="coerce").astype(float),
            "detalle": "← " + tr["cuenta_emisora"].astype(str) + tr["comentario"].fillna("").map(lambda c: f" ({c})" if str(c).strip() else "")
        })
        x["ts"] = tr["ts"]
        df_u = pd.concat([df_u, x], ignore_index=True)

    if not inc.empty:
        x = pd.DataFrame({
            "fecha":  inc["fecha_dt"].dt.date,
            "tipo":   "Ingreso",
            "monto":  pd.to_numeric(inc["monto"], errors="coerce").astype(float),
            "detalle": inc["categoria"].fillna("").astype(str) + inc["nota"].fillna("").map(lambda n: f" — {n}" if str(n).strip() else "")
        })
        x["ts"] = inc["ts"]
        df_u = pd.concat([df_u, x], ignore_index=True)

    # Ordenar por fecha desc y ts desc; tomar sólo los últimos 7
    if not df_u.empty:
        df_u["ts"] = pd.to_numeric(df_u["ts"], errors="coerce").fillna(0).astype(int)
        df_u = df_u.sort_values(by=["fecha","ts"], ascending=[False, False]).head(7)

        st.caption("Últimos 7 movimientos (más recientes arriba)")
        if AG_OK:
            gb = GridOptionsBuilder.from_dataframe(df_u[["fecha","tipo","monto","detalle"]])
            gb.configure_default_column(resizable=True, filter=True, sortable=True)
            gb.configure_column("monto", type=["numericColumn"], valueFormatter="x.toLocaleString('es-MX',{style:'currency',currency:'MXN'})")
            AgGrid(df_u[["fecha","tipo","monto","detalle"]],
                   gridOptions=gb.build(),
                   fit_columns_on_grid_load=True,
                   update_mode=GridUpdateMode.NO_UPDATE,
                   height=260, theme="streamlit")
        else:
            df_fmt = df_u.copy()
            df_fmt["monto"] = df_fmt["monto"].map(lambda x: f"${x:,.2f}")
            st.dataframe(df_fmt[["fecha","tipo","monto","detalle"]], use_container_width=True, hide_index=True)
    else:
        st.info("Sin movimientos en el rango seleccionado.")

    # --- Curva de saldo reconstruida (sin cambios) ---
    s = get_saldos(); saldo_actual = s.get(nombre, 0.0)
    movs=[]
    for dframe, sign in [
        (g,  lambda v:-abs(float(v))),
        (te, lambda v:-abs(float(v))),
        (tr, lambda v:+abs(float(v))),
        (inc,lambda v:+abs(float(v))),
    ]:
        if not dframe.empty:
            for _, row in dframe.iterrows():
                try: movs.append((pd.to_datetime(row["fecha_dt"]).date(), sign(row["monto"])))
                except: pass
    if movs:
        dfm = pd.DataFrame(movs, columns=["fecha","delta"]).groupby("fecha", as_index=False)["delta"].sum().sort_values("fecha")
        saldo_ini = saldo_actual - dfm["delta"].sum()
        fechas = pd.date_range(desde, date.today(), freq="D")
        pts=[]; j=0; running=saldo_ini
        for f in fechas:
            while j<len(dfm) and dfm.iloc[j]["fecha"]<=f.date():
                running += dfm.iloc[j]["delta"]; j+=1
            pts.append({"fecha":f.date(), "saldo":running})
        serie = pd.DataFrame(pts)

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=serie["fecha"], y=serie["saldo"], mode="lines",
            line=dict(width=3, color=PRIMARY),
            hovertemplate="<b>%{x}</b><br>Saldo: $%{y:,.2f}<extra></extra>"
        ))
        fig.update_layout(margin=dict(l=10,r=10,t=10,b=10), height=260, template="simple_white",
                          xaxis=dict(title="", showgrid=False),
                          yaxis=dict(title="", showgrid=True, gridcolor="rgba(0,0,0,.06)"))
        st.plotly_chart(fig, use_container_width=True)

        delta = float(serie["saldo"].iloc[-1] - serie["saldo"].iloc[0])
        if delta >= 0:
            st.success(f"Subió ${delta:,.2f} en el período.")
        else:
            st.warning(f"Bajó ${abs(delta):,.2f} en el período.")
    else:
        st.info("Sin movimientos para graficar.")

with st.expander("BBVA Concentradora"): detalle("BBVA Concentradora")
with st.expander("BBVA Credito"):       detalle("BBVA Credito")
with st.expander("NU"):                 detalle("NU")
with st.expander("GBM"):                detalle("GBM")

# ==========================
#   Bottom nav (móvil)
# ==========================
st.markdown("""
<div class="bottom-nav">
  <button onclick="window.scrollTo({top:0,behavior:'smooth'})">Arriba</button>
  <button onclick="document.querySelectorAll('.section-title')[2]?.scrollIntoView({behavior:'smooth'})">Nuevo</button>
  <button onclick="window.scrollTo({top:document.body.scrollHeight,behavior:'smooth'})">Abajo</button>
</div>
""", unsafe_allow_html=True)















