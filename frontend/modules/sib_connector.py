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
    from modules.nombres_comunes import enriquecer_nombres_comunes

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
        df_out = enriquecer_nombres_comunes(df_out, col_cientifico="Especie", col_comun="Nombre Común")
        return df_out.reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

def renderizar_tablero_sib(nombre_seleccion: str, nivel_escala: str):
    """Renderiza el tablero completo de Biodiversidad en Cifras (SiB Colombia)."""
    nivel_up = str(nivel_escala or "").upper()

    # Aviso explícito para Barrios (sin registros oficiales en SiB)
    if "BARRIO" in nivel_up:
        df_gbif_mem = st.session_state.get("bio_gbif_df")
        n_gbif_barrio = len(df_gbif_mem) if (
            isinstance(df_gbif_mem, pd.DataFrame)
            and not df_gbif_mem.empty
            and st.session_state.get("bio_gbif_terr") == nombre_seleccion
        ) else 0

        st.info(
            f"ℹ️ **Escala de Barrio ({nombre_seleccion}):** El portal *Biodiversidad en Cifras* (SiB Colombia) "
            "solo consolida estadísticas oficiales a escala **Municipal y Departamental**. "
            "Sin embargo, nuestra plataforma sí realiza **intersección espacial directa con el polígono del barrio** "
            "en la pestaña **🗺️ Mapa & GBIF** para detectar observaciones puntuales geolocalizadas."
        )
        if n_gbif_barrio > 0:
            st.success(
                f"🟢 Ya se detectaron **{n_gbif_barrio} registros puntuales en GBIF** dentro del polígono de "
                f"**{nombre_seleccion}**. Puedes explorarlos en **🗺️ Mapa & GBIF** y **🧬 Taxonomía**."
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

def renderizar_cruce_ecohidrologico(nombre_seleccion: str, nivel_escala: str):
    """Fase 3: Cruce entre Holdridge (Tab 4), Déficit Ripario (Tab 7) y Cifras Oficiales SiB."""
    from modules.nombres_comunes import obtener_paleta_por_zona_vida

    st.subheader(f"🌱 Cruce Eco-Hidrológico y Priorización de Restauración — {nombre_seleccion}")
    st.caption(
        "Integra el piso térmico dominante (Holdridge), el déficit de bosque ripario y las especies "
        "amenazadas e invasoras registradas por el SiB Colombia para orientar la restauración ecológica."
    )

    slug, etiqueta = resolver_slug_sib(nombre_seleccion, nivel_escala)

    # 1. Lectura de insumos desde memoria viva (Aleph)
    zv_dom = st.session_state.get("aleph_zona_vida_dom", "Bosque húmedo Montano Bajo (bh-MB)")
    ha_deficit = float(st.session_state.get("ha_deficit_ripario") or 0.0)
    ha_potencial = float(st.session_state.get("aleph_ha_pastos") or 0.0)

    # Si aún no se ha corrido Tab 7 (Ecología del Paisaje), usamos el potencial de restauración como referencia
    area_meta_base = ha_deficit if ha_deficit > 0 else max(10.0, ha_potencial * 0.15)
    origen_area = "Déficit Ripario exacto (Tab 7)" if ha_deficit > 0 else "Estimación base (15% de pasturas)"

    # Reutilizamos el resumen ya cacheado (evita 3 descargas pesadas por cada cambio de territorio)
    resumen = obtener_resumen_region_sib(slug)
    df_grupos, _ = obtener_grupos_biologicos_sib(slug, tipo="biologico")
    reinos_base = df_grupos[
        df_grupos["Grupo"].isin(["Plantas", "Animales", "Hongos", "Bacterias", "Protozoos", "Cromistas"])
    ] if not df_grupos.empty else pd.DataFrame()

    n_am = int(resumen.get("especies_amenazadas_nacional_total") or (reinos_base["Amenazadas Nal (Res.0126)"].sum() if not reinos_base.empty else 0))
    n_end = int(resumen.get("especies_endemicas") or (reinos_base["Endémicas"].sum() if not reinos_base.empty else 0))
    n_inv = int(resumen.get("especies_exoticas_total") or (reinos_base["Exóticas/Invasoras"].sum() if not reinos_base.empty else 0))

    # Índice compuesto de prioridad (0 - 100)
    score_bio = min(50.0, (n_am * 0.35) + (n_end * 0.08))
    score_hidro = min(50.0, (area_meta_base / 50.0) * 50.0) if area_meta_base > 0 else 15.0
    indice_prioridad = min(100.0, round(score_bio + score_hidro, 1))
    nivel_prio = "🔴 Crítica" if indice_prioridad >= 70 else "🟠 Alta" if indice_prioridad >= 45 else "🟢 Moderada"

    # KPIs de síntesis
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Índice de Prioridad", f"{indice_prioridad:.0f} / 100", nivel_prio)
    c2.metric("Piso Térmico Dominante", obtener_paleta_por_zona_vida(zv_dom)[0], str(zv_dom)[:28])
    c3.metric("Meta de Restauración", f"{area_meta_base:,.1f} ha", origen_area)
    c4.metric("Presión Biológica (SiB)", f"{n_am} Amenazadas", f"{n_end} Endémicas · {n_inv} Exóticas")

    st.divider()

    # 2. Simulador de Diseño de Restauración
    col_cfg, col_pal = st.columns([1, 1.8], gap="large")

    with col_cfg:
        st.markdown("##### 📐 Parámetros de Intervención")
        ha_intervenir = st.number_input(
            "Hectáreas a restaurar:",
            min_value=1.0,
            value=float(round(area_meta_base, 1)),
            step=5.0,
            key="f3_ha_rest",
        )
        densidad_arb = st.slider("Densidad de siembra (árboles/ha):", 400, 1600, 1100, step=100, key="f3_dens")
        costo_ha_usd = st.number_input("Costo integral por hectárea (USD):", min_value=500.0, value=2500.0, step=250.0, key="f3_costo")

        total_arboles = int(ha_intervenir * densidad_arb)
        presupuesto_usd = ha_intervenir * costo_ha_usd

        st.success(
            f"🌳 **Meta Operativa:** Se requieren **{total_arboles:,} árboles nativos** "
            f"con una inversión estimada de **${presupuesto_usd:,.0f} USD**."
        )

    with col_pal:
        cod_zv, paleta = obtener_paleta_por_zona_vida(zv_dom)
        st.markdown(f"##### 🌿 Paleta de Especies Nativas Sugeridas ({cod_zv})")
        df_paleta = pd.DataFrame(paleta, columns=["Especie", "Nombre Común", "Rol Eco-Hidrológico"])
        st.dataframe(df_paleta, use_container_width=True, hide_index=True)

        if n_inv > 0:
            if st.button(f"⚠️ Ver alerta de especies exóticas/invasoras ({etiqueta})", key=f"btn_inv_{slug}"):
                df_inv = obtener_especies_tematica_sib(slug, "exoticas-total")
                if not df_inv.empty:
                    top_inv = df_inv.head(5)
                    lista_inv = ", ".join(
                        f"*{r['Especie']}* ({r['Nombre Común']})" if r.get("Nombre Común", "—") != "—" else f"*{r['Especie']}*"
                        for _, r in top_inv.iterrows()
                    )
                    st.warning(f"⚠️ **Control previo sugerido:** {lista_inv}.")