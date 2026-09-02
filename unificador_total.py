import pandas as pd

print("Iniciando la fusión de las matrices curadas de Antioquia...")

try:
    # 1. Leer los tres archivos maestros limpios 
    # (Agregamos sep=';' y utf-8-sig para que lea perfectamente los CSV guardados desde Excel)
    df_bov = pd.read_csv("Censo_Maestro_Bovinos.csv", sep=';', encoding='utf-8-sig')
    df_por = pd.read_csv("Censo_Maestro_Porcinos.csv", sep=';', encoding='utf-8-sig')
    df_ave = pd.read_csv("Censo_Maestro_Aves.csv", sep=';', encoding='utf-8-sig')

    # Limpieza preventiva: Quitar espacios accidentales en los nombres de las columnas
    df_bov.columns = df_bov.columns.str.strip().str.upper()
    df_por.columns = df_por.columns.str.strip().str.upper()
    df_ave.columns = df_ave.columns.str.strip().str.upper()

    # 2. Extraer y renombrar columnas para Bovinos
    df_bov = df_bov[['AÑO', 'MUNICIPIO', 'TOTAL_BOVINOS', 'TOTAL_FINCAS_BOVINOS']].copy()
    df_bov.rename(columns={'AÑO': 'Anio', 'MUNICIPIO': 'Municipio_Norm', 'TOTAL_BOVINOS': 'Bovinos'}, inplace=True)

    # 3. Extraer y renombrar columnas para Porcinos
    df_por = df_por[['AÑO', 'MUNICIPIO', 'TOTAL_CERDOS', 'TOTAL_PREDIOS_PORCICOLAS']].copy()
    df_por.rename(columns={'AÑO': 'Anio', 'MUNICIPIO': 'Municipio_Norm', 'TOTAL_CERDOS': 'Porcinos'}, inplace=True)

    # 4. Extraer y renombrar columnas para Aves
    df_ave = df_ave[['AÑO', 'MUNICIPIO', 'TOTAL_AVES', 'TOTAL_PREDIOS_AVICOLAS']].copy()
    df_ave.rename(columns={'AÑO': 'Anio', 'MUNICIPIO': 'Municipio_Norm', 'TOTAL_AVES': 'Aves'}, inplace=True)

    # 5. Fusionar todo en una sola tabla maestra perfecta
    df_final = pd.merge(df_bov, df_por, on=['Anio', 'Municipio_Norm'], how='outer')
    df_final = pd.merge(df_final, df_ave, on=['Anio', 'Municipio_Norm'], how='outer')

    # 6. Rellenar vacíos con ceros para evitar errores matemáticos
    df_final.fillna(0, inplace=True)

    # 7. Asegurar que todos los conteos sean números enteros
    columnas_numericas = ['Bovinos', 'Porcinos', 'Aves', 'TOTAL_FINCAS_BOVINOS', 'TOTAL_PREDIOS_PORCICOLAS', 'TOTAL_PREDIOS_AVICOLAS']
    for col in columnas_numericas:
        df_final[col] = df_final[col].astype(int)

    # 8. Exportar
    nombre_final = "Censo_Pecuario_Historico_Completo.csv"
    df_final.to_csv(nombre_final, index=False, encoding='utf-8-sig')
    print(f"\n¡Éxito total! Archivo '{nombre_final}' creado con {len(df_final)} filas.")
    print("El archivo está listo para ser subido a Supabase.")

except Exception as e:
    print(f"Error durante la consolidación: {e}")