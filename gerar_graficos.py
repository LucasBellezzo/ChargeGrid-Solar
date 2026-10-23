"""Gera os graficos do README a partir dos CSV/JSON produzidos por simulador.py."""
import csv
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

pasta = sys.argv[1] if len(sys.argv) > 1 else "resultados"
img = os.path.join(pasta, "img")
os.makedirs(img, exist_ok=True)


def ler(nome):
    with open(os.path.join(pasta, nome), encoding="utf-8") as f:
        return list(csv.DictReader(f))


# 1) dia ensolarado: potencia ao longo do dia
for slug, titulo in [("dia_ensolarado", "Dia ensolarado"),
                     ("dia_chuvoso", "Dia chuvoso")]:
    d = ler(f"serie_{slug}.csv")
    h = [float(r["hora"]) for r in d]
    ger = [int(r["geracao_w"]) for r in d]
    out = [int(r["carga_outras_w"]) for r in d]
    sol = [int(r["recarga_solar_w"]) for r in d]
    red = [int(r["recarga_rede_w"]) for r in d]
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.stackplot(h, sol, red, labels=["Recarga - solar (W)", "Recarga - rede (W)"],
                 colors=["#2e9e5b", "#d9a400"], alpha=0.85)
    ax.plot(h, ger, color="#1f5fbf", lw=1.6, label="Geração solar disponível (W)")
    ax.plot(h, out, color="#b03030", lw=1.6, ls="--", label="Carga das outras estações (W)")
    ax.set_xlim(0, 24)
    ax.set_xticks(range(0, 25, 3))
    ax.set_xlabel("Hora do dia")
    ax.set_ylabel("Potência (W)")
    ax.set_title(f"{titulo} - decisão do ChargeGrid (simulado)")
    ax.legend(loc="upper left", fontsize=8)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(os.path.join(img, f"perfil_{slug}.png"), dpi=140)
    plt.close(fig)

# 2) comparação entre cenários: kWh solar vs rede
res = json.load(open(os.path.join(pasta, "resumo_cenarios.json"), encoding="utf-8"))
nomes = [r["cenario"].replace(" com ", "\ncom ").replace("parcialmente ", "parcialmente\n")
         for r in res]
solar = [r["solar_kwh"] for r in res]
rede = [r["rede_kwh"] for r in res]
fig, ax = plt.subplots(figsize=(9, 4.2))
x = range(len(res))
ax.bar(x, solar, color="#2e9e5b", label="Solar (kWh)")
ax.bar(x, rede, bottom=solar, color="#d9a400", label="Rede (kWh)")
for i, r in enumerate(res):
    ax.text(i, solar[i] + rede[i] + 0.5, f"{r['pct_solar']}% solar", ha="center", fontsize=9)
ax.set_xticks(list(x))
ax.set_xticklabels(nomes, fontsize=8)
ax.set_ylabel("Energia entregue na recarga (kWh/dia)")
ax.set_title("Origem da energia da recarga por cenário (simulado)")
ax.set_ylim(0, max(a + b for a, b in zip(solar, rede)) * 1.15)
ax.legend()
ax.grid(axis="y", alpha=0.25)
fig.tight_layout()
fig.savefig(os.path.join(img, "comparativo_cenarios.png"), dpi=140)
plt.close(fig)
print("ok")
