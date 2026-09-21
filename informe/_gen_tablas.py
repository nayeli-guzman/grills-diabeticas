# -*- coding: utf-8 -*-
import pandas as pd

def esc(s):
    s = str(s)
    return (s.replace('&', r'\&').replace('%', r'\%').replace('_', r'\_')
             .replace('#', r'\#').replace('$', r'\$')
             .replace('✔', r'\ok').replace('✘', r'\fail')
             .replace('≥', r'$\geq$').replace('≤', r'$\leq$').replace('×', r'$\times$')
             .replace('∈', r'$\in$').replace('—', '---').replace('−', '-').replace('<', r'$<$'))

ROW = " & ".join(["{}"] * 8) + r" \\" + "\n"

# 1) Tabla modelos (Fase 3, E1 estatico) ------------------------------------
m = pd.read_csv("../resultados/fase3_resumen_modelos.csv")
with open("tabla_modelos.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n")
    f.write(r"\centering\small" + "\n")
    f.write(r"\begin{tabular}{lccccccc}" + "\n")
    f.write(r"\toprule" + "\n")
    f.write(r"Modelo & ROC-AUC & PR-AUC & lift & Brier & BSS & pend. cal. & ECE \\" + "\n")
    f.write(r"\midrule" + "\n")
    for _, r in m.iterrows():
        nombre = r"\textbf{" + r["modelo"] + "}" if r["modelo"] == "RandomForest" else r["modelo"]
        f.write(f"{nombre} & {r.ROC_AUC:.3f} & {r.PR_AUC:.3f} & {r.lift_PR:.2f}" + r"$\times$"
                + f" & {r.Brier:.3f} & {r.BSS:.3f} & {r.pendiente_cal:.3f} & {r.ECE:.3f}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n")
    f.write(r"\end{tabular}" + "\n")
    f.write(r"\caption{Comparación de modelos, experimento E1 (estático, entrenado en bloques 1--2, "
            r"evaluado sin reentrenar en bloques 3--10). Modelo principal en negrita.}" + "\n")
    f.write(r"\label{tab:modelos}" + "\n")
    f.write(r"\end{table}" + "\n")

# 2) Tabla resumen de drift (PSI) -------------------------------------------
d = pd.read_csv("../resultados/drift_por_bloque.csv")
counts = d["estado PSI"].value_counts()
alerta = d[d["estado PSI"] == "ALERTA"].sort_values(["bloque", "PSI"], ascending=[True, False])
with open("tabla_drift_resumen.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\begin{minipage}{0.42\textwidth}" + "\n" + r"\centering" + "\n")
    f.write(r"\begin{tabular}{lr}" + "\n" + r"\toprule" + "\n")
    f.write(r"Estado PSI & \# (variable, bloque) \\" + "\n" + r"\midrule" + "\n")
    for k in ["estable", "vigilar", "ALERTA"]:
        f.write(f"{k} & {int(counts.get(k, 0))}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n" + r"\end{minipage}%" + "\n")
    f.write(r"\begin{minipage}{0.55\textwidth}" + "\n" + r"\centering" + "\n")
    f.write(r"\begin{tabular}{clc}" + "\n" + r"\toprule" + "\n")
    f.write(r"Bloque & Variable en ALERTA & PSI \\" + "\n" + r"\midrule" + "\n")
    for _, r in alerta.iterrows():
        f.write(f"{int(r.bloque)} & {esc(r.variable)} & {r.PSI:.3f}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n" + r"\end{minipage}" + "\n")
    f.write(r"\caption{Izquierda: conteo de pares (variable, bloque) por estado de PSI respecto a B1 "
            r"(131 estables, 14 en vigilancia, 8 en alerta, sobre 13 variables $\times$ 9 bloques evaluados). "
            r"Derecha: alertas (PSI $>0.25$), concentradas en \texttt{number\_diagnoses\_capped} y "
            r"\texttt{admission\_type\_grp} desde el bloque 7--8 en adelante.}" + "\n")
    f.write(r"\label{tab:drift-resumen}" + "\n" + r"\end{table}" + "\n")

# 3) Tabla estrategias E1-E4 (bloques comunes >=6) ---------------------------
t = pd.read_csv("../resultados/experimentos_E1_E4.csv")
comunes = [b for b in t.bloque.unique() if b >= 6]
c = (t[t.bloque.isin(comunes)]
     .groupby("experimento")[["ROC_AUC", "PR_AUC", "Brier", "pendiente_cal"]]
     .mean().round(3).reset_index())
ESTRATEGIA = "E3 deslizante S=3"
with open("tabla_estrategias.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\begin{tabular}{lcccc}" + "\n" + r"\toprule" + "\n")
    f.write(r"Estrategia & ROC-AUC & PR-AUC & Brier & pend. cal. \\" + "\n" + r"\midrule" + "\n")
    for _, r in c.sort_values("PR_AUC", ascending=False).iterrows():
        nombre = r"\textbf{" + esc(r["experimento"]) + "}" if r["experimento"] == ESTRATEGIA else esc(r["experimento"])
        f.write(f"{nombre} & {r.ROC_AUC:.3f} & {r.PR_AUC:.3f} & {r.Brier:.3f} & {r.pendiente_cal:.3f}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n")
    f.write(r"\caption{Comparación de estrategias de adaptación sobre bloques comunes (6--10). "
            r"\textbf{E3 deslizante $S=3$} obtiene el mejor PR-AUC promedio entre E1/E2/E3 y se elige "
            r"como estrategia desplegada para la capa de decisión --- coincide con la ventana de "
            r"reentrenamiento de tamaño 3 propuesta originalmente en el plan de trabajo. E4 (disparador) "
            r"se muestra por separado por ser condicional a los reentrenamientos que dispara "
            r"(1 evento en el horizonte evaluado).}" + "\n")
    f.write(r"\label{tab:estrategias}" + "\n" + r"\end{table}" + "\n")

# 4) Tabla costos -------------------------------------------------------------
cc = pd.read_csv("../resultados/costos_politicas.csv", index_col=0)
with open("tabla_costos.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\resizebox{\textwidth}{!}{%" + "\n")
    f.write(r"\begin{tabular}{lrrrrr}" + "\n" + r"\toprule" + "\n")
    f.write(r"Escenario & Modelo (3 cat.) & No intervenir & Intervenir a todos & Binario ($p\geq p^*$) & Ahorro vs. mejor ref. \\" + "\n")
    f.write(r"\midrule" + "\n")
    for idx, r in cc.iterrows():
        f.write(f"{esc(idx)} & \\${r['Modelo (3 categorías)']:,.0f} & \\${r['No intervenir']:,.0f} & "
                f"\\${r['Intervenir a todos']:,.0f} & \\${r['Modelo binario (p ≥ p*, sin cupo)']:,.0f} & "
                f"\\${r['Ahorro vs mejor referencia']:,.0f}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}}" + "\n")
    f.write(r"\caption{Costo esperado por cada 1,000 altas (US\$), promedio sobre bloques de decisión, "
            r"bajo la estrategia adaptativa desplegada.}" + "\n")
    f.write(r"\label{tab:costos}" + "\n" + r"\end{table}" + "\n")

# 5) Tabla caso de negocio -----------------------------------------------------
r = pd.read_csv("../resultados/caso_negocio_resumen.csv", index_col=0)["valor"]
b = pd.read_csv("../resultados/caso_negocio_por_bloque.csv")
altas = f'{int(r["altas_anuales_supuesto"]):,}'
with open("tabla_caso_negocio.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\begin{tabular}{lr}" + "\n" + r"\toprule" + "\n")
    f.write(f"Concepto & Valor anual (US\\$, {altas} altas/año) \\\\" + "\n")
    f.write(r"\midrule" + "\n")
    f.write(r"Costo esperado \textbf{sin} monitoreo (estático, umbral fijo) & \$"
            + f'{r["costo_sin_monitoreo_anual_usd"]:,.0f}' + r" \\" + "\n")
    f.write(r"Costo esperado \textbf{con} monitoreo adaptativo (E3, $S=3$) & \$"
            + f'{r["costo_con_monitoreo_anual_usd"]:,.0f}' + r" \\" + "\n")
    f.write(r"\textbf{Ahorro bruto atribuible al monitoreo de drift} & \textbf{\$"
            + f'{r["ahorro_bruto_anual_usd"]:,.0f}' + r"} \\" + "\n")
    f.write(r"Costo de mantenimiento del sistema (monitoreo + reentrenos) & \$"
            + f'{r["costo_mantenimiento_anual_usd"]:,.0f}' + r" \\" + "\n")
    f.write(r"\textbf{Beneficio neto} & \textbf{\$" + f'{r["beneficio_neto_anual_usd"]:,.0f}' + r"} \\" + "\n")
    f.write(r"Retorno sobre la inversión (ROI) & " + f'{r["roi_x"]:.0f}' + r"x \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n")
    f.write(r"\caption{Caso de negocio anualizado (supuesto de escala: " + altas + r" altas/año). "
            r"El ahorro bruto surge de comparar, bloque a bloque, la misma simulación de costos de la "
            r"Sección de capa de decisión bajo dos políticas: modelo estático sin monitoreo vs. "
            r"estrategia adaptativa E3 ($S=3$) disparada por el módulo de drift.}" + "\n")
    f.write(r"\label{tab:caso-negocio}" + "\n" + r"\end{table}" + "\n")
    f.write("\n" + r"\bigskip" + "\n")
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\begin{tabular}{lrrr}" + "\n" + r"\toprule" + "\n")
    f.write(r"Bloque (pseudo-año de prueba) & Costo/1,000 sin monitoreo & Costo/1,000 con monitoreo & Ahorro/1,000 \\" + "\n")
    f.write(r"\midrule" + "\n")
    for _, row in b.iterrows():
        f.write(f"{int(row.bloque)} & \\${row.costo_1000_sin_monitoreo:,.0f} & "
                f"\\${row.costo_1000_con_monitoreo:,.0f} & \\${row.ahorro_1000:,.0f}" + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n")
    f.write(r"\caption{Ahorro por cada 1,000 altas, bloque a bloque. El ahorro crece de \$924 (bloque 4) "
            r"a \$15,114 (bloque 10) --- más de 16$\times$ --- a medida que el drift se acumula y la "
            r"brecha entre el modelo estático y el adaptativo se agranda: el valor del monitoreo aumenta "
            r"con el tiempo, no es constante.}" + "\n")
    f.write(r"\label{tab:caso-negocio-bloque}" + "\n" + r"\end{table}" + "\n")

# 6) Tabla equidad --------------------------------------------------------------
e = pd.read_csv("../resultados/equidad.csv")
with open("tabla_equidad.tex", "w", encoding="utf-8") as f:
    f.write(r"\begin{table}[H]" + "\n" + r"\centering\small" + "\n")
    f.write(r"\begin{tabular}{llrrccc}" + "\n" + r"\toprule" + "\n")
    f.write(r"Dimensión & Grupo & n & Reingresos & Tasa reingreso & Razón FNR & Cumple FNR \\" + "\n")
    f.write(r"\midrule" + "\n")
    for _, r in e.iterrows():
        razon = f'{r["razón_FNR"]:.2f}' if pd.notna(r["razón_FNR"]) else "---"
        cumple = r"\ok" if r["cumple_FNR"] is True else (r"\fail" if r["evaluable"] else "n/e")
        tasa = f'{r.tasa_reingreso*100:.1f}\\%'
        f.write(f'{esc(r["dimensión"])} & {esc(r["grupo"])} & {int(r.n):,} & {int(r.reingresos):,} & '
                f'{tasa} & {razon} & {cumple}' + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n" + r"\end{tabular}" + "\n")
    f.write(r"\caption{Auditoría de equidad por grupo etario y raza. ``n/e'' = no evaluable ($<$100 "
            r"reingresos). En la muestra evaluada, todos los grupos evaluables cumplen igualdad de "
            r"oportunidad (razón de FNR). La razón de \emph{selección} a Alto Riesgo entre subgrupos "
            r"(regla del 80\%) sí incumple (mínimo observado $\approx$0.38) por el mecanismo de cupo "
            r"global --- ver discusión en la Sección de criterios no cumplidos.}" + "\n")
    f.write(r"\label{tab:equidad}" + "\n" + r"\end{table}" + "\n")

# 7) Tabla resumen de criterios (completa) --------------------------------------
rc = pd.read_csv("../resultados/resumen_criterios.csv")
with open("tabla_resumen_criterios.tex", "w", encoding="utf-8") as f:
    f.write(r"{\footnotesize" + "\n")
    f.write(r"\begin{longtable}{p{1.5cm}p{3.2cm}p{3.0cm}p{4.2cm}c}" + "\n")
    f.write(r"\toprule" + "\n")
    f.write(r"\textbf{Dimensión} & \textbf{Métrica} & \textbf{Criterio} & \textbf{Resultado} & \textbf{Cumple} \\" + "\n")
    f.write(r"\midrule" + "\n" + r"\endhead" + "\n")
    for _, r in rc.iterrows():
        cumple = {"✔": r"\ok", "✘": r"\fail", "—": "---"}.get(r["Cumple"], esc(r["Cumple"]))
        f.write(f'{esc(r["Dimensión"])} & {esc(r["Métrica"])} & {esc(r["Criterio"])} & {esc(r["Resultado"])} & {cumple}' + r" \\" + "\n")
    f.write(r"\bottomrule" + "\n")
    f.write(r"\caption{Tabla resumen de criterios de aprobación, estrategia desplegada (E3, $S=3$). "
            r"18 de 23 criterios cuantitativos se cumplen; los 5 restantes se discuten en el texto.}" + "\n")
    f.write(r"\label{tab:resumen-criterios}" + "\n")
    f.write(r"\end{longtable}}" + "\n")

print("Tablas generadas OK")
