#!/usr/bin/env python3
"""Genera un informe HTML (imprimible en PDF) a partir de los CSV de medir-wifi.ps1.

Uso:
    python3 analizar.py datos/mediciones.csv [otros.csv ...] --salida informe.html
        [--nombre "José Luis Aybar"] [--habitacion "214"] [--contratado 300]

Requiere pandas y matplotlib.
"""
from __future__ import annotations

import argparse
import base64
import html
import io
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

# Paleta (modo claro, pensada para imprimir)
AZUL, NARANJA, AQUA, ROJO = "#2a78d6", "#eb6834", "#1baf7a", "#e34948"
TINTA, TINTA2, REJILLA, FONDO = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"

# Referencias externas (ver README para las fuentes)
MIN_LEGAL = 10.0          # Mbps bajada, servicio universal (Ley 11/2022, art. 37)
ZOOM_BAJADA = 3.8         # Mbps, videollamada de grupo 1080p (Zoom)
ZOOM_SUBIDA = 3.0
DESCARGAS = [             # (descripción, MB)
    ("PyTorch para CPU (paquete pip para Windows, ~124 MB)", 124),
    ("PyTorch con CUDA (paquete conda para Windows, ~1,3 GB)", 1300),
    ("Dataset o modelo de IA de tamaño medio (ejemplo: 5 GB)", 5000),
]
WEBS = ["prado", "ugr", "github", "pypi", "google", "wikipedia"]

plt.rcParams.update({
    "figure.facecolor": FONDO, "axes.facecolor": FONDO, "savefig.facecolor": FONDO,
    "axes.edgecolor": REJILLA, "axes.labelcolor": TINTA2, "xtick.color": TINTA2,
    "ytick.color": TINTA2, "axes.grid": True, "grid.color": REJILLA, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False, "font.size": 9.5,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlecolor": TINTA,
    "axes.titlelocation": "left", "legend.frameon": False,
})


# --------------------------------------------------------------------------- datos
def cargar(rutas: list[Path]) -> pd.DataFrame:
    df = pd.concat([pd.read_csv(r, encoding="utf-8-sig") for r in rutas], ignore_index=True)
    df["fecha"] = pd.to_datetime(df["fecha_hora"])
    df = df.sort_values("fecha").drop_duplicates(["fecha_hora", "lugar"]).reset_index(drop=True)
    for c in df.columns:
        if c.endswith(("_mbps", "_ms", "_pct", "_s", "_ghz")) or c in ("dns_fallos", "web_fallos", "hay_conexion"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["lugar"] = df["lugar"].fillna("sin-indicar").astype(str)
    df["bajada"] = df[["bajada_cloudflare_mbps", "bajada_ovh_mbps"]].max(axis=1)
    df["subida"] = df["subida_mbps"]
    df["sin_conexion"] = df["hay_conexion"].fillna(1).eq(0)
    # Si el ping falla siempre pero las descargas funcionan, la red bloquea el ping: no es pérdida.
    bloqueado = df["inet_perdida_pct"].eq(100) & df["bajada"].notna()
    for c in ("inet_ping_ms", "inet_jitter_ms", "inet_ping_max_ms", "inet_perdida_pct"):
        df.loc[bloqueado, c] = np.nan
    df["ping_bloqueado"] = bloqueado
    return df


def resumen(g: pd.DataFrame) -> dict:
    con = g[~g["sin_conexion"]]
    bajada_o_cero = g["bajada"].where(~g["sin_conexion"], 0.0)
    subida_o_cero = g["subida"].where(~g["sin_conexion"], 0.0)
    q = lambda s, p: float(s.quantile(p)) if s.notna().any() else np.nan  # noqa: E731
    return {
        "n": len(g),
        "desde": g["fecha"].min(), "hasta": g["fecha"].max(),
        "bajada_med": q(con["bajada"], .5), "bajada_p10": q(con["bajada"], .1),
        "bajada_min": float(con["bajada"].min()) if con["bajada"].notna().any() else np.nan,
        "bajada_max": float(con["bajada"].max()) if con["bajada"].notna().any() else np.nan,
        "subida_med": q(con["subida"], .5), "subida_p10": q(con["subida"], .1),
        "ping_med": q(con["inet_ping_ms"], .5), "jitter_med": q(con["inet_jitter_ms"], .5),
        "perdida_media": float(con["inet_perdida_pct"].mean()) if con["inet_perdida_pct"].notna().any() else np.nan,
        "router_ping_med": q(con["router_ping_ms"], .5),
        "router_perdida_media": float(con["router_perdida_pct"].mean()) if con["router_perdida_pct"].notna().any() else np.nan,
        "web_med": q(con["web_media_s"], .5), "web_p90": q(con["web_media_s"], .9),
        "senal_med": q(con["wifi_senal_pct"], .5),
        "pct_sin_conexion": 100 * g["sin_conexion"].mean(),
        "pct_bajo_legal": 100 * (bajada_o_cero.fillna(0) < MIN_LEGAL).mean(),
        "pct_bajo_zoom": 100 * ((bajada_o_cero.fillna(0) < ZOOM_BAJADA) | (subida_o_cero.fillna(0) < ZOOM_SUBIDA)).mean(),
        "banda": con["wifi_banda_ghz"].mode().iloc[0] if con["wifi_banda_ghz"].notna().any() else np.nan,
        "puntos_acceso": con["wifi_bssid"].dropna().nunique() if "wifi_bssid" in con else 0,
        "ping_bloqueado": bool(g["ping_bloqueado"].all()),
    }


# ------------------------------------------------------------------------ formato
def num(x, d=1, suf=""):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "—"
    return f"{x:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf


def duracion(seg: float) -> str:
    if not np.isfinite(seg):
        return "—"
    if seg < 90:
        return f"{seg:.0f} s"
    if seg < 5400:
        return f"{seg / 60:.0f} min"
    h, m = divmod(round(seg / 60), 60)
    return f"{h} h {m:02d} min"


def fecha_es(d: pd.Timestamp) -> str:
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    return f"{dias[d.weekday()]} {d.day:02d}/{d.month:02d} {d:%H:%M}"


def png(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode()


def etiqueta_linea(ax, y, texto):
    ax.axhline(y, color=TINTA2, lw=1, ls=(0, (4, 3)), zorder=1)
    ax.annotate(texto, xy=(1, y), xycoords=("axes fraction", "data"), xytext=(4, 0),
                textcoords="offset points", va="center", fontsize=8, color=TINTA2)


def eje_fechas(ax):
    ax.xaxis.set_major_locator(mdates.AutoDateLocator(minticks=4, maxticks=9))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%H:%M"))


# ----------------------------------------------------------------------- gráficas
def graf_velocidad(g: pd.DataFrame, contratado: float | None) -> str:
    fig, ax = plt.subplots(figsize=(9, 3.6))
    con = g[~g["sin_conexion"]]
    ax.plot(con["fecha"], con["bajada"], color=AZUL, lw=2, marker="o", ms=3, label="Bajada")
    ax.plot(con["fecha"], con["subida"], color=NARANJA, lw=2, marker="o", ms=3, label="Subida")
    cortes = g[g["sin_conexion"]]
    if len(cortes):
        ax.scatter(cortes["fecha"], np.zeros(len(cortes)), marker="x", s=50, color=ROJO, lw=2,
                   label=f"Sin conexión ({len(cortes)})", zorder=5, clip_on=False)
    etiqueta_linea(ax, MIN_LEGAL, "10 Mbps · mínimo legal\nservicio universal")
    if contratado:
        etiqueta_linea(ax, contratado, f"{num(contratado, 0)} Mbps · contratado")
    ax.set_ylim(bottom=0)
    ax.set_ylabel("Mbps")
    ax.set_title("Velocidad medida a lo largo del tiempo")
    eje_fechas(ax)
    ax.legend(loc="upper left", ncol=3)
    return png(fig)


def graf_horas(g: pd.DataFrame) -> str | None:
    con = g[~g["sin_conexion"]].copy()
    if con["bajada"].notna().sum() < 12:
        return None
    con["hora"] = con["fecha"].dt.hour
    h = con.groupby("hora")["bajada"].median().reindex(range(24))
    fig, ax = plt.subplots(figsize=(9, 2.8))
    ax.bar(h.index, h.values, color=AZUL, width=0.8)
    etiqueta_linea(ax, MIN_LEGAL, "10 Mbps")
    ax.set_xticks(range(0, 24, 2), [f"{i:02d}h" for i in range(0, 24, 2)])
    ax.set_xlim(-0.6, 23.6)
    ax.set_ylabel("Mbps (mediana)")
    ax.set_title("Velocidad de bajada según la hora del día")
    ax.grid(axis="x", visible=False)
    return png(fig)


def graf_latencia(g: pd.DataFrame) -> str | None:
    con = g[~g["sin_conexion"]]
    if con["inet_ping_ms"].notna().sum() < 2 and con["router_ping_ms"].notna().sum() < 2:
        return None
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(9, 4.2), sharex=True, gridspec_kw={"height_ratios": [3, 2]})
    if con["inet_ping_ms"].notna().any():
        a1.plot(con["fecha"], con["inet_ping_ms"], color=AZUL, lw=2, marker="o", ms=3, label="Ping a internet (1.1.1.1)")
    if con["router_ping_ms"].notna().any():
        a1.plot(con["fecha"], con["router_ping_ms"], color=AQUA, lw=2, marker="o", ms=3, label="Ping al router / punto de acceso")
    a1.set_ylim(bottom=0)
    a1.set_ylabel("ms")
    a1.set_title("Latencia (ping) y pérdida de paquetes")
    a1.legend(loc="upper left", ncol=2)
    if con["inet_perdida_pct"].notna().any():
        a2.plot(con["fecha"], con["inet_perdida_pct"], color=AZUL, lw=2, marker="o", ms=3, label="Internet")
    if con["router_perdida_pct"].notna().any():
        a2.plot(con["fecha"], con["router_perdida_pct"], color=AQUA, lw=2, marker="o", ms=3, label="Router")
    a2.set_ylim(bottom=0)
    a2.set_ylabel("% perdidos")
    eje_fechas(a2)
    return png(fig)


def graf_lugares(res_lugar: dict[str, dict]) -> str | None:
    if len(res_lugar) < 2:
        return None
    nombres = list(res_lugar)
    med = [res_lugar[k]["bajada_med"] for k in nombres]
    fig, ax = plt.subplots(figsize=(9, 0.55 * len(nombres) + 1))
    y = np.arange(len(nombres))
    ax.barh(y, med, color=AZUL, height=0.6)
    for yi, v, k in zip(y, med, nombres):
        ax.annotate(f"{num(v)} Mbps  (n={res_lugar[k]['n']})", xy=(0 if np.isnan(v) else v, yi),
                    xytext=(4, 0), textcoords="offset points", va="center", fontsize=8.5, color=TINTA)
    ax.set_yticks(y, nombres)
    ax.invert_yaxis()
    ax.set_xlabel("Mbps de bajada (mediana)")
    ax.set_title("Comparativa por lugar o tipo de conexión")
    ax.grid(axis="y", visible=False)
    ax.set_xlim(0, np.nanmax(med) * 1.35 if np.isfinite(np.nanmax(med)) else 1)
    return png(fig)


def graf_senal(g: pd.DataFrame) -> str | None:
    con = g[~g["sin_conexion"]].dropna(subset=["wifi_senal_pct", "bajada"])
    if len(con) < 8:
        return None
    fig, ax = plt.subplots(figsize=(9, 3))
    ax.scatter(con["wifi_senal_pct"], con["bajada"], color=AZUL, s=36, edgecolor=FONDO, lw=1.5)
    etiqueta_linea(ax, MIN_LEGAL, "10 Mbps")
    ax.set_xlim(0, 100)
    ax.set_ylim(bottom=0)
    ax.set_xlabel("Señal wifi (%) según Windows")
    ax.set_ylabel("Mbps de bajada")
    ax.set_title("¿Depende de la cobertura? Señal frente a velocidad")
    return png(fig)


# -------------------------------------------------------------------- diagnóstico
def lectura(df: pd.DataFrame, principal: str, res: dict[str, dict]) -> list[str]:
    r = res[principal]
    g = df[df["lugar"] == principal]
    out = []
    b = r["bajada_med"]
    if np.isfinite(b) and b < MIN_LEGAL:
        out.append(f"La velocidad mediana de bajada en <b>{html.escape(principal)}</b> es de <b>{num(b)} Mbps</b>, "
                   f"por debajo de los 10 Mbps que la Ley 11/2022 General de Telecomunicaciones fija como velocidad "
                   f"mínima del servicio universal de banda ancha en España.")
    if r["pct_bajo_legal"] > 0:
        out.append(f"El <b>{num(r['pct_bajo_legal'], 0)} %</b> de las mediciones (contando los cortes) quedó por "
                   f"debajo de 10 Mbps de bajada.")
    if r["pct_bajo_zoom"] > 0:
        out.append(f"En el <b>{num(r['pct_bajo_zoom'], 0)} %</b> de las mediciones la conexión no llegaba a lo que Zoom "
                   f"recomienda para una videollamada de grupo en 1080p (3,8 Mbps de bajada y 3,0 de subida).")
    if r["pct_sin_conexion"] > 0:
        out.append(f"Hubo <b>{int(round(r['pct_sin_conexion'] * r['n'] / 100))} mediciones sin conexión</b> "
                   f"({num(r['pct_sin_conexion'], 0)} % del total).")
    if np.isfinite(r["ping_med"]) and (r["ping_med"] > 60 or (np.isfinite(r["perdida_media"]) and r["perdida_media"] > 1)):
        out.append(f"La latencia mediana a internet es de {num(r['ping_med'], 0)} ms con una pérdida media de paquetes "
                   f"del {num(r['perdida_media'])} %. Esto hace que las webs tarden en responder aunque la velocidad "
                   f"parezca aceptable, porque cada página necesita decenas de peticiones.")
    rp, rl = r["router_ping_med"], r["router_perdida_media"]
    lento = np.isfinite(b) and b < MIN_LEGAL * 3
    if np.isfinite(rp) and lento:
        if rp < 10 and (not np.isfinite(rl) or rl < 1):
            out.append(f"El enlace entre el portátil y el router o punto de acceso responde bien ({num(rp, 0)} ms). "
                       f"Eso apunta a que el cuello de botella está más allá: el punto de acceso o la línea a internet "
                       f"de la residencia no dan abasto.")
        elif rp >= 20 or (np.isfinite(rl) and rl >= 2):
            out.append(f"Ya el enlace hasta el router o punto de acceso es deficiente ({num(rp, 0)} ms y "
                       f"{num(rl)} % de pérdida), lo que apunta a cobertura insuficiente, interferencias o un punto "
                       f"de acceso saturado en esta zona.")
    s = r["senal_med"]
    if np.isfinite(s) and lento:
        if s >= 60:
            out.append(f"La señal wifi en la habitación es buena (mediana {num(s, 0)} %). Por tanto, la lentitud no se "
                       f"explica por la distancia ni por la antena del portátil.")
        elif s < 40:
            out.append(f"La señal wifi en la habitación es débil (mediana {num(s, 0)} %): la zona está mal cubierta.")
    if r["banda"] == 2.4 and lento:
        out.append("El portátil estuvo conectado casi siempre en la banda de 2,4 GHz, que es la más lenta y la que más "
                   "se satura cuando hay muchos usuarios.")
    con = g[~g["sin_conexion"]].copy()
    if con["bajada"].notna().sum() >= 24:
        con["franja"] = pd.cut(con["fecha"].dt.hour, [-1, 7, 13, 19, 23],
                               labels=["madrugada (0-7h)", "mañana (8-13h)", "tarde (14-19h)", "noche (20-23h)"])
        f = con.groupby("franja", observed=True)["bajada"].median().dropna()
        if len(f) >= 2 and f.min() < 0.5 * f.max():
            out.append(f"La velocidad cambia mucho según la hora: <b>{num(f.min())} Mbps</b> de mediana por la "
                       f"{f.idxmin()} frente a {num(f.max())} Mbps por la {f.idxmax()}. Es el patrón típico de una red "
                       f"que se satura cuando la usan muchos residentes a la vez.")
    cf, ovh = con["bajada_cloudflare_mbps"].median(), con["bajada_ovh_mbps"].median()
    if np.isfinite(cf) and np.isfinite(ovh) and max(cf, ovh) > 0 and min(cf, ovh) / max(cf, ovh) > 0.5:
        out.append(f"Los dos servidores de prueba, de empresas distintas (Cloudflare: {num(cf)} Mbps; OVH: {num(ovh)} Mbps), "
                   f"dan resultados parecidos. El problema no está en un servidor concreto.")
    for k, rk in res.items():
        if k == principal or not np.isfinite(rk["bajada_med"]) or not np.isfinite(b):
            continue
        kl = k.lower()
        if "movil" in kl or "datos" in kl:
            if rk["bajada_med"] > 2 * b:
                out.append(f"Con el mismo portátil conectado a datos móviles se obtienen {num(rk['bajada_med'])} Mbps "
                           f"(n={rk['n']}), {num(rk['bajada_med'] / max(b, 0.01), 0)} veces más. El portátil no es el problema.")
        elif "router" in kl or "comun" in kl or "salon" in kl:
            if rk["bajada_med"] < 1.5 * b:
                out.append(f"Incluso en «{html.escape(k)}» la velocidad sigue siendo baja ({num(rk['bajada_med'])} Mbps, "
                           f"n={rk['n']}). No es solo cuestión de distancia.")
            elif rk["bajada_med"] > 2 * b:
                out.append(f"En «{html.escape(k)}» se obtienen {num(rk['bajada_med'])} Mbps (n={rk['n']}), mucho más que en "
                           f"la habitación. La zona de la habitación necesita mejor cobertura.")
        elif "cable" in kl and rk["bajada_med"] > 2 * b:
            out.append(f"Por cable se obtienen {num(rk['bajada_med'])} Mbps (n={rk['n']}). La línea tiene capacidad; "
                       f"lo que falla es el wifi.")
    return out


# --------------------------------------------------------------------------- HTML
CSS = """
@page { size: A4; margin: 16mm 14mm; }
:root { color-scheme: light; --tinta:#0b0b0b; --tinta2:#52514e; --rejilla:#e4e3df; --fondo:#fcfcfb; --acento:#2a78d6; }
* { box-sizing: border-box; }
body { margin: 0; background: var(--fondo); color: var(--tinta); font: 10.5pt/1.5 system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; }
main { max-width: 820px; margin: 0 auto; padding: 24px 16px 48px; }
h1 { font-size: 20pt; margin: 0 0 4px; line-height: 1.2; }
h2 { font-size: 13pt; margin: 28px 0 8px; padding-top: 8px; border-top: 1px solid var(--rejilla); }
.sub { color: var(--tinta2); margin: 0 0 16px; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 10px; margin: 16px 0; }
.kpi { border: 1px solid var(--rejilla); border-radius: 8px; padding: 10px 12px; break-inside: avoid; }
.kpi b { display: block; font-size: 17pt; line-height: 1.15; font-variant-numeric: tabular-nums; }
.kpi span { color: var(--tinta2); font-size: 9pt; }
table { width: 100%; border-collapse: collapse; font-size: 9.5pt; font-variant-numeric: tabular-nums; margin: 8px 0; }
th, td { text-align: left; padding: 5px 8px; border-bottom: 1px solid var(--rejilla); vertical-align: top; }
th { color: var(--tinta2); font-weight: 600; }
td.n, th.n { text-align: right; }
img { width: 100%; height: auto; display: block; margin: 8px 0 4px; break-inside: avoid; }
ul.lectura li { margin-bottom: 6px; }
.nota { color: var(--tinta2); font-size: 9pt; }
.tabla-scroll { overflow-x: auto; }
"""


def construir_html(df, res, principal, lect, imgs, args) -> str:
    r = res[principal]
    e = html.escape
    filas_lugar = "".join(
        f"<tr><td>{e(k)}</td><td class=n>{v['n']}</td><td class=n>{num(v['bajada_med'])}</td>"
        f"<td class=n>{num(v['bajada_p10'])}</td><td class=n>{num(v['subida_med'])}</td>"
        f"<td class=n>{num(v['ping_med'], 0)}</td><td class=n>{num(v['perdida_media'])}</td>"
        f"<td class=n>{num(v['web_med'], 2)}</td><td class=n>{num(v['pct_sin_conexion'], 0)}</td></tr>"
        for k, v in res.items())
    ref = 100.0
    filas_desc = "".join(
        f"<tr><td>{e(d)}</td><td class=n>{duracion(mb * 8 / r['bajada_med']) if r['bajada_med'] > 0 else '—'}</td>"
        f"<td class=n>{duracion(mb * 8 / r['bajada_p10']) if r['bajada_p10'] > 0 else '—'}</td>"
        f"<td class=n>{duracion(mb * 8 / ref)}</td></tr>"
        for d, mb in DESCARGAS)
    g = df[df["lugar"] == principal]
    webs = "".join(
        f"<tr><td>{w}</td><td class=n>{num(g[f'web_{w}_s'].median(), 2)} s</td>"
        f"<td class=n>{num(g[f'web_{w}_s'].quantile(.9), 2)} s</td>"
        f"<td class=n>{int(g[f'web_{w}_s'].isna().sum())}</td></tr>"
        for w in WEBS if f"web_{w}_s" in g)
    bloque = lambda k: f'<img alt="" src="data:image/png;base64,{imgs[k]}">' if imgs.get(k) else ""  # noqa: E731
    quien = " · ".join(x for x in [args.nombre, f"Habitación {args.habitacion}" if args.habitacion else ""] if x)
    contratado = (f"<p>Velocidad de referencia indicada: <b>{num(args.contratado, 0)} Mbps</b>. "
                  f"La mediana medida equivale al <b>{num(100 * r['bajada_med'] / args.contratado, 0)} %</b> de esa cifra.</p>"
                  if args.contratado else "")
    ping_nota = ("<p class=nota>La red no responde al ping (ICMP) hacia internet, así que la latencia no se ha podido medir; "
                 "no se ha contado como pérdida.</p>" if r["ping_bloqueado"] else "")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Informe de conexión</title><style>{CSS}</style></head><body><main>
<h1>Informe de la conexión a internet</h1>
<p class=sub>{e(quien) + ' · ' if quien else ''}Mediciones automáticas del {fecha_es(r['desde'])} al {fecha_es(r['hasta'])}
({r['n']} mediciones en «{e(principal)}»). Generado el {datetime.now():%d/%m/%Y}.</p>

<div class=kpis>
<div class=kpi><b>{num(r['bajada_med'])} Mbps</b><span>bajada (mediana)</span></div>
<div class=kpi><b>{num(r['bajada_p10'])} Mbps</b><span>bajada en el peor 10 % de las mediciones</span></div>
<div class=kpi><b>{num(r['subida_med'])} Mbps</b><span>subida (mediana)</span></div>
<div class=kpi><b>{num(r['pct_bajo_legal'], 0)} %</b><span>mediciones por debajo de 10 Mbps</span></div>
<div class=kpi><b>{num(r['ping_med'], 0)} ms</b><span>ping mediano a internet</span></div>
<div class=kpi><b>{num(r['web_med'], 1)} s</b><span>respuesta media de webs (mediana)</span></div>
</div>
{contratado}{ping_nota}

<h2>Qué muestran los datos</h2>
<ul class=lectura>{''.join(f'<li>{x}</li>' for x in lect) or '<li>No hay datos suficientes para extraer conclusiones.</li>'}</ul>

<h2>Evolución</h2>
{bloque('vel')}{bloque('horas')}{bloque('lat')}

<h2>Comparativas</h2>
{bloque('lugares')}{bloque('senal')}
<div class=tabla-scroll><table>
<tr><th>Lugar / conexión</th><th class=n>Mediciones</th><th class=n>Bajada mediana (Mbps)</th><th class=n>Bajada peor 10 %</th>
<th class=n>Subida mediana</th><th class=n>Ping (ms)</th><th class=n>Pérdida %</th><th class=n>Webs (s)</th><th class=n>% sin conexión</th></tr>
{filas_lugar}</table></div>

<h2>Impacto en el trabajo de la carrera</h2>
<p>El grado en Ciencia de Datos e Inteligencia Artificial requiere descargar con frecuencia librerías, entornos y conjuntos de datos,
trabajar con repositorios Git y servicios en la nube, y seguir clases, tutorías y trabajos en grupo por videollamada.
Tiempo estimado de algunas descargas habituales con la conexión medida:</p>
<div class=tabla-scroll><table>
<tr><th>Descarga</th><th class=n>Con la mediana medida</th><th class=n>En el peor 10 %</th><th class=n>A 100 Mbps (referencia)</th></tr>
{filas_desc}</table></div>
<p>Tiempo de respuesta de páginas que uso a diario (solo la página principal; con imágenes y scripts, una carga real tarda más):</p>
<div class=tabla-scroll><table>
<tr><th>Web</th><th class=n>Mediana</th><th class=n>Peor 10 %</th><th class=n>Fallos</th></tr>
{webs}</table></div>

<h2>Método y límites</h2>
<p class=nota>Cada medición la hace automáticamente un script de PowerShell desde el portátil
(<code>medir-wifi.ps1</code>). Registra los datos del wifi según Windows, el ping al router y a 1.1.1.1 y 8.8.8.8 (20 y 10 paquetes),
el tiempo de DNS, la bajada contra dos servidores independientes (Cloudflare y OVH; se toma el <b>mejor</b> de los dos),
la subida (Cloudflare) y el tiempo de respuesta de seis webs. Cada prueba de bajada dura como máximo 12 s o 20 MB, así que
el script ocupa la red solo alrededor de un 2-3 % del tiempo. Los resultados describen la conexión desde este portátil y este
lugar; el wifi puede variar de una habitación a otra. Las mediciones sin conexión se cuentan como 0 Mbps en los porcentajes,
pero no en las medianas.<br>
Referencias: Ley 11/2022 General de Telecomunicaciones, art. 37 (servicio universal: 10 Mbit/s de bajada);
requisitos de ancho de banda de Zoom (support.zoom.com, artículo KB0060748); tamaños de paquetes de PyTorch publicados en PyPI y anaconda.org.</p>
</main></body></html>"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv", nargs="+", type=Path)
    ap.add_argument("--salida", type=Path, default=Path("informe-wifi.html"))
    ap.add_argument("--nombre", default="")
    ap.add_argument("--habitacion", default="")
    ap.add_argument("--contratado", type=float, default=None, help="Mbps prometidos o contratados, si se conocen")
    ap.add_argument("--principal", default=None, help="lugar principal (por defecto, el de más mediciones)")
    args = ap.parse_args()

    df = cargar(args.csv)
    orden = df["lugar"].value_counts()
    principal = args.principal or orden.index[0]
    res = {principal: resumen(df[df["lugar"] == principal])}
    for k in orden.index:
        if k != principal:
            res[k] = resumen(df[df["lugar"] == k])
    g = df[df["lugar"] == principal]
    imgs = {"vel": graf_velocidad(g, args.contratado), "horas": graf_horas(g), "lat": graf_latencia(g),
            "lugares": graf_lugares(res), "senal": graf_senal(g)}
    lect = lectura(df, principal, res)
    args.salida.write_text(construir_html(df, res, principal, lect, imgs, args), encoding="utf-8")

    r = res[principal]
    print(f"Informe: {args.salida}")
    print(f"Lugar principal: {principal} · {r['n']} mediciones · {fecha_es(r['desde'])} → {fecha_es(r['hasta'])}")
    print(f"Bajada mediana {num(r['bajada_med'])} Mbps (peor 10 %: {num(r['bajada_p10'])}) · "
          f"subida {num(r['subida_med'])} · ping {num(r['ping_med'], 0)} ms · pérdida {num(r['perdida_media'])} % · "
          f"{num(r['pct_bajo_legal'], 0)} % bajo 10 Mbps · {num(r['pct_sin_conexion'], 0)} % sin conexión")
    for x in lect:
        print(" -", html.unescape(x.replace("<b>", "").replace("</b>", "")))


if __name__ == "__main__":
    main()
