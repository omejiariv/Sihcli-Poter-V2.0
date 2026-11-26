# frontend/modules/sib_connector.py
import unicodedata
import re
import requests
import pandas as pd
import plotly.express as px
import streamlit as st

SIB_BASE_URL = "https://cifras.biodiversidad.co/api"

TEMATICAS_SIB = {
    "amenazadas-nacional": "🚨 Amenazadas Nacional (Res. 0126/2024)",
    "amenazadas-global": "🌍 Amenazadas Global (UICN)",
    "endemicas": "🇨🇴 Endémicas de Colombia",
    "cites": "📜 CITES (Comercio Regulado)",
    "exoticas-total": "⚠️ Exóticas e Invasoras",
    "migratorias": "🦅 Migratorias (Aves)",
}


def _norm(texto: str) -> str:
    if not texto or pd.isna(texto):
        return ""
    s = unicodedata.normalize("NFD", str(texto).upper().strip())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^A-Z0-9\s]", "", s).strip()


@st.cache_data(ttl=86400, show_spinner=False, max_entries=2)
def obtener_catalogo_municipios_sib():
    """Descarga el catálogo oficial de los 125 municipios de Antioquia con su slug y DANE."""
    url = f"{SIB_BASE_URL}/sibdata?region=antioquia&tipo=registros&indicador=registros_region_total&subregiones=1"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            return {}, pd.DataFrame()
        df = pd.DataFrame(data)
        mapa = {}
        for _, row in df.iterrows():
            slug = str(row.get("slug_region", "")).strip()
            lbl = _norm(row.get("label_region") or row.get("label") or "")
            if slug and lbl:
                mapa[lbl] = slug
        # Alias comunes en Antioquia
        alias = {
            "EL PENOL": mapa.get("PENOL", "penol"),
            "EL RETIRO": mapa.get("RETIRO", "retiro"),
            "CAROLINA DEL PRINCIPE": mapa.get("CAROLINA", "carolina"),
            "SAN VICENTE": mapa.get("SAN VICENTE FERRER", "san-vicente-ferrer"),
            "CARMEN DE VIBORAL": mapa.get("EL CARMEN DE VIBORAL", "el-carmen-de-viboral"),
            "SANTAFE DE ANTIOQUIA": mapa.get("SANTA FE DE ANTIOQUIA", "santa-fe-de-antioquia"),
            "BOLIVAR": mapa.get("CIUDAD BOLIVAR", "ciudad-bolivar"),
            "PUEBLO RICO": mapa.get("PUEBLORRICO", "pueblorrico"),
        }
        mapa.update(alias)
        return mapa, df
    except Exception:
        return {}, pd.DataFrame()


def resolver_slug_sib(nombre_territorio: str, nivel_escala: str):
    """Devuelve (slug_sib, etiqueta_mostrada) para Antioquia o cualquiera de sus 125 municipios."""
    nivel_up = str(nivel_escala or "").upper()
    terr_norm = _norm(nombre_territorio)

    if "DEPARTAMENT" in nivel_up or "NACION" in nivel_up or terr_norm == "ANTIOQUIA":
        return "antioquia", "Antioquia (Departamental)"

    mapa_mpios, _ = obtener_catalogo_municipios_sib()

    # Si es Vereda, Comuna o Barrio, usamos el municipio padre del Aleph
    if any(k in nivel_up for k in ["VEREDA", "COMUNA", "BARRIO"]):
        mpio_padre = st.session_state.get("aleph_municipio_padre", "MEDELLIN")
        p_norm = _norm(mpio_padre)
        if p_norm in mapa_mpios:
            return mapa_mpios[p_norm], f"{mpio_padre.title()} (Municipio de referencia)"

    # Búsqueda directa municipal
    if terr_norm in mapa_mpios:
        return mapa_mpios[terr_norm], nombre_territorio.title()

    # Fallback para cuencas, regiones o CARs -> contexto departamental Antioquia
    return "antioquia", "Antioquia (Referencia Departamental)"


@st.cache_data(ttl=86400, show_spinner=False, max_entries=15)
def obtener_resumen_region_sib(slug: str) -> dict:
    """Obtiene métricas generales de la región (especies observadas, estimadas, registros)."""
    url = f"{SIB_BASE_URL}/regions/{slug}?lean=1"
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        return r.json() if isinstance(r.json(), dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=86400, show_spinner=False, max_entries=15)
def obtener_grupos_biologicos_sib(slug: str, tipo: str = "biologico"):
    """Descarga cifras por grupo biológico o de interés de conservación."""
    url = f"{SIB_BASE_URL}/regions/{slug}/grupos?tipo={tipo}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        raw = r.json()
        if not isinstance(raw, list) or not raw:
            return pd.DataFrame(), []

        filas = []
        for g in raw:
            filas.append({
                "Grupo": str(g.get("slug_grupo") or g.get("slug") or "").replace("-", " ").title(),
                "Slug": g.get("slug_grupo") or g.get("slug"),
                "Especies": int(g.get("especies_region_total") or 0),
                "Registros": int(g.get("registros_region_total") or 0),
                "Amenazadas Nal (Res.0126)": int(g.get("especies_amenazadas_nacional_total") or 0),
                "CR Nal": int(g.get("especies_amenazadas_nacional_cr") or 0),
                "EN Nal": int(g.get("especies_amenazadas_nacional_en") or 0),
                "VU Nal": int(g.get("especies_amenazadas_nacional_vu") or 0),
                "Amenazadas UICN": int(g.get("especies_amenazadas_global_total") or 0),
                "Endémicas": int(g.get("especies_endemicas") or 0),
                "CITES": int(g.get("especies_cites_total") or 0),
                "Exóticas/Invasoras": int(g.get("especies_exoticas_total") or 0),
                "Migratorias": int(g.get("especies_migratorias") or 0),
            })
        df = pd.DataFrame(filas).sort_values("Especies", ascending=False).reset_index(drop=True)
        return df, raw
    except Exception:
        return pd.DataFrame(), []


@st.cache_data(ttl=86400, show_spinner=False, max_entries=15)
def obtener_especies_tematica_sib(slug: str, tematica: str = "amenazadas-nacional") -> pd.DataFrame:
    """Descarga el listado oficial de especies para una temática de conservación."""
    url = f"{SIB_BASE_URL}/species?region={slug}&tematica={tematica}"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        data = r.json()
        if not isinstance(data, list) or not data:
            return pd.DataFrame()
        df = pd.DataFrame(data)
        cols_map = {
            "especie": "Especie",
            "vernacular_name_es": "Nombre Común",
            "clase": "Clase",
            "orden": "Orden",
            "familia": "Familia",
            "observaciones": "Observaciones",
            "url_gbif": "GBIF",
            "url_cbc": "Catálogo SiB",
        }
        cols_ok = [c for c in cols_map if c in df.columns]
        df_out = df[cols_ok].rename(columns=cols_map)
        if "Observaciones" in df_out.columns:
            df_out = df_out.sort_values("Observaciones", ascending=False)
        return df_out.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


def renderizar_tablero_sib(nombre_seleccion: str, nivel_escala: str):
    """Renderiza el tablero completo de Biodiversidad en Cifras (SiB Colombia)."""
    nivel_up = str(nivel_escala or "").upper()

    # Aviso explícito para Barrios (sin registros oficiales en SiB)
    if "BARRIO" in nivel_up:
        st.warning(
            f"ℹ️ **Sin registros oficiales para {nombre_seleccion}:** "
            "El SiB Colombia no cuenta con cifras oficiales desagregadas a escala de barrio. "
            "Puedes buscar observaciones puntuales en vivo en la pestaña **🗺️ Mapa & GBIF**, "
            "o cambiar a escala **Municipal (Medellín)** para ver el consolidado oficial."
        )
        return

    slug, etiqueta = resolver_slug_sib(nombre_seleccion, nivel_escala)

    st.subheader(f"🇨🇴 Biodiversidad en Cifras — {etiqueta}")
    st.caption("Fuente oficial en vivo: **SiB Colombia** (`cifras.biodiversidad.co`) · Resolución 0126/2024 MinAmbiente & Lista Roja UICN.")

    if any(k in nivel_up for k in ["VEREDA", "COMUNA"]):
        st.info(
            f"ℹ️ **Nota de escala:** El SiB Colombia publica estadísticas oficiales a nivel municipal y departamental. "
            f"No existen cifras oficiales exclusivas para **{nombre_seleccion}**; se muestra el consolidado de **{etiqueta}**. "
            f"Para registros puntuales dentro del polígono exacto, usa la pestaña **🗺️ Mapa & GBIF**."
        )

    with st.spinner(f"📡 Consultando cifras oficiales del SiB Colombia para {etiqueta}..."):
        resumen = obtener_resumen_region_sib(slug)
        df_grupos, _ = obtener_grupos_biologicos_sib(slug, tipo="biologico")

    if not resumen and df_grupos.empty:
        st.warning(f"ℹ️ No se tienen registros oficiales del SiB Colombia para **{etiqueta}** en este momento.")
        return

    # 1. KPIs Principales (con respaldo por reinos principales si lean=1 omite totales)
    reinos_base = df_grupos[
        df_grupos["Grupo"].isin(["Plantas", "Animales", "Hongos", "Bacterias", "Protozoos", "Cromistas"])
    ] if not df_grupos.empty else pd.DataFrame()

    esp_obs = int(resumen.get("especies_region_total") or (reinos_base["Especies"].sum() if not reinos_base.empty else 0))
    reg_tot = int(resumen.get("registros_region_total") or (reinos_base["Registros"].sum() if not reinos_base.empty else 0))
    am_nal = int(resumen.get("especies_amenazadas_nacional_total") or (reinos_base["Amenazadas Nal (Res.0126)"].sum() if not reinos_base.empty else 0))
    endem = int(resumen.get("especies_endemicas") or (reinos_base["Endémicas"].sum() if not reinos_base.empty else 0))
    cites = int(resumen.get("especies_cites_total") or (reinos_base["CITES"].sum() if not reinos_base.empty else 0))
    exot = int(resumen.get("especies_exoticas_total") or (reinos_base["Exóticas/Invasoras"].sum() if not reinos_base.empty else 0))

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("🌿 Especies", f"{esp_obs:,}")
    k2.metric("📍 Observaciones", f"{reg_tot:,}")
    k3.metric("🚨 Amenazadas (Nal)", f"{am_nal:,}")
    k4.metric("🇨🇴 Endémicas", f"{endem:,}")
    k5.metric("📜 CITES", f"{cites:,}")
    k6.metric("⚠️ Exóticas/Inv.", f"{exot:,}")

    st.divider()

    # 2. Gráfico por Grupos Biológicos
    if not df_grupos.empty:
        c_g1, c_g2 = st.columns([1.4, 1])
        with c_g1:
            top_g = df_grupos[df_grupos["Especies"] > 0].head(12)
            fig_g = px.bar(
                top_g,
                x="Especies",
                y="Grupo",
                orientation="h",
                color="Amenazadas Nal (Res.0126)",
                color_continuous_scale="YlOrRd",
                title=f"Riqueza por Grupo Biológico ({etiqueta})",
                height=420,
            )
            fig_g.update_layout(yaxis={"categoryorder": "total ascending"}, margin=dict(l=10, r=10, t=40, b=10))
            st.plotly_chart(fig_g, use_container_width=True)

        with c_g2:
            st.markdown("##### 📋 Resumen por Grupo")
            cols_ver = ["Grupo", "Especies", "Amenazadas Nal (Res.0126)", "Endémicas", "Exóticas/Invasoras"]
            st.dataframe(df_grupos[cols_ver], use_container_width=True, hide_index=True, height=380)

    st.divider()

    # 3. Explorador de Especies por Temática (Bajo Demanda)
    st.markdown("##### 🔎 Listado Oficial de Especies por Temática de Conservación")
    tem_sel = st.selectbox(
        "Selecciona una temática para consultar el listado oficial:",
        options=list(TEMATICAS_SIB.keys()),
        format_func=lambda k: TEMATICAS_SIB[k],
        key=f"sib_tem_{slug}",
    )

    with st.spinner("Descargando listado oficial de especies..."):
        df_esp = obtener_especies_tematica_sib(slug, tem_sel)

    if not df_esp.empty:
        st.caption(f"Mostrando **{len(df_esp):,} especies** registradas en **{etiqueta}** para *{TEMATICAS_SIB[tem_sel]}*.")
        st.dataframe(
            df_esp,
            use_container_width=True,
            hide_index=True,
            column_config={
                "GBIF": st.column_config.LinkColumn("GBIF", display_text="Ver en GBIF"),
                "Catálogo SiB": st.column_config.LinkColumn("Catálogo SiB", display_text="Ficha SiB"),
            },
        )
        csv_sib = df_esp.to_csv(index=False).encode("utf-8")
        st.download_button(
            "💾 Descargar Listado Oficial SiB (CSV)",
            csv_sib,
            f"sib_{slug}_{tem_sel}.csv",
            "text/csv",
            key=f"dl_sib_{slug}_{tem_sel}",
        )
    else:
        st.info("No se encontraron registros para esta temática en el territorio seleccionado.")