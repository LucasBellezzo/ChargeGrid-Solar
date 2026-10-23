"""
Sprint 4 - Simulador de cenarios do ChargeGrid (Challenge FIAP + GoodWe 2026).

Reproduz EXATAMENTE a logica de decisao de `calcularFornecimento()` do main.py
(Sprint 3, Raspberry Pi Pico / MicroPython) e a executa sobre perfis diarios de
geracao solar e de carga das outras estacoes, para obter resultados
quantitativos reprodutiveis (kWh solar vs rede, % renovavel, CO2 evitado, etc).

Tudo aqui e SIMULADO: os perfis de geracao/carga sao modelos sinteticos, nao
medicoes de um inversor GoodWe real. As constantes de potencia sao as mesmas do
main.py. Fatores de CO2 e tarifa sao PREMISSAS editaveis (ver abaixo).

Uso:  python simulador.py [pasta_de_saida]
"""
import csv
import json
import math
import os
import sys

# ----- constantes identicas ao main.py (Sprint 3) -----
GERACAO_MAX_W = 4000
CARGA_MAX_OUTRAS_ESTACOES_W = 3000
DEMANDA_RECARGA_W = 3000
CAPACIDADE_REDE_MAX_W = 3500

# ----- premissas da analise (editaveis; NAO sao dados medidos) -----
FATOR_CO2_REDE_KG_POR_KWH = 0.04   # ordem de grandeza da media do SIN brasileiro
TARIFA_REDE_R_POR_KWH = 0.90       # tarifa hipotetica comercial, apenas ilustrativa
PASSO_MIN = 1                      # resolucao da simulacao (minutos)
JANELA_RECARGA = (8, 20)           # horario em que ha sessao de recarga ativa (h)


def calcular_fornecimento(geracao_solar, carga_outras):
    """Copia fiel de calcularFornecimento() do main.py."""
    capacidade_total = geracao_solar + CAPACIDADE_REDE_MAX_W
    sobra = max(0, capacidade_total - carga_outras)
    entrega = min(DEMANDA_RECARGA_W, sobra)

    solar_restante = max(0, geracao_solar - carga_outras)
    entrega_solar = min(entrega, solar_restante)
    entrega_rede = entrega - entrega_solar

    if entrega < DEMANDA_RECARGA_W:
        estado = "REDUZIDA"
    elif entrega_rede == 0:
        estado = "100_SOLAR"
    else:
        estado = "SOLAR_REDE"
    return {"estado": estado, "solar": entrega_solar, "rede": entrega_rede}


# ----- perfis sinteticos -----
def solar_w(hora, fator_nuvem=1.0, nuvens=None):
    """Curva em sino entre 6h e 18h, pico ao meio-dia, escalada pelo cenario."""
    if hora < 6 or hora > 18:
        return 0.0
    base = math.sin(math.pi * (hora - 6) / 12) ** 1.3
    f = fator_nuvem
    if nuvens:
        for (ini, fim, red) in nuvens:
            if ini <= hora < fim:
                f *= red
    return GERACAO_MAX_W * base * f


def carga_outras_w(hora, pico_alto=False):
    """Carga das demais estacoes do posto: manha moderada, pico no fim da tarde."""
    base = 600 + 500 * math.exp(-((hora - 9.5) ** 2) / 4)
    base += (1800 if not pico_alto else 2600) * math.exp(-((hora - 18.0) ** 2) / 2.2)
    base += 350 * math.exp(-((hora - 12.5) ** 2) / 1.5)
    return min(CARGA_MAX_OUTRAS_ESTACOES_W, base)


CENARIOS = {
    "Dia ensolarado": dict(fator_nuvem=1.0, pico_alto=False),
    "Dia parcialmente nublado": dict(
        fator_nuvem=0.75, pico_alto=False,
        nuvens=[(10, 11.5, 0.35), (13, 14.5, 0.3)]),
    "Dia chuvoso": dict(fator_nuvem=0.18, pico_alto=False),
    "Dia ensolarado com pico de carga": dict(fator_nuvem=1.0, pico_alto=True),
}


def simular(nome, params):
    linhas = []
    kwh = dict(solar=0.0, rede=0.0, demanda=0.0)
    min_estado = {"100_SOLAR": 0, "SOLAR_REDE": 0, "REDUZIDA": 0}
    pico_rede_w = 0.0
    passos = int(24 * 60 / PASSO_MIN)
    for i in range(passos):
        hora = i * PASSO_MIN / 60
        ger = solar_w(hora, params["fator_nuvem"], params.get("nuvens"))
        carga = carga_outras_w(hora, params["pico_alto"])
        sessao = JANELA_RECARGA[0] <= hora < JANELA_RECARGA[1]
        d = calcular_fornecimento(ger, carga)
        entrega = d["solar"] + d["rede"] if sessao else 0
        sol = d["solar"] if sessao else 0
        red = d["rede"] if sessao else 0
        dt_h = PASSO_MIN / 60
        if sessao:
            kwh["solar"] += sol * dt_h / 1000
            kwh["rede"] += red * dt_h / 1000
            kwh["demanda"] += DEMANDA_RECARGA_W * dt_h / 1000
            min_estado[d["estado"]] += PASSO_MIN
        # importacao total da rede pelo posto (outras estacoes + recarga)
        rede_total = max(0, carga - ger) + red
        pico_rede_w = max(pico_rede_w, rede_total)
        assert rede_total <= CAPACIDADE_REDE_MAX_W + 1e-6, "limite de rede violado"
        linhas.append(dict(
            hora=round(hora, 3), geracao_w=round(ger), carga_outras_w=round(carga),
            sessao=int(sessao), estado=d["estado"] if sessao else "SEM_SESSAO",
            recarga_solar_w=round(sol), recarga_rede_w=round(red),
            rede_total_posto_w=round(rede_total)))
    entregue = kwh["solar"] + kwh["rede"]
    res = {
        "cenario": nome,
        "demanda_kwh": round(kwh["demanda"], 2),
        "entregue_kwh": round(entregue, 2),
        "solar_kwh": round(kwh["solar"], 2),
        "rede_kwh": round(kwh["rede"], 2),
        "pct_solar": round(100 * kwh["solar"] / entregue, 1) if entregue else 0.0,
        "pct_demanda_atendida": round(100 * entregue / kwh["demanda"], 1),
        "min_100_solar": min_estado["100_SOLAR"],
        "min_solar_rede": min_estado["SOLAR_REDE"],
        "min_reduzida": min_estado["REDUZIDA"],
        "pico_importacao_rede_w": round(pico_rede_w),
        "co2_evitado_kg": round(kwh["solar"] * FATOR_CO2_REDE_KG_POR_KWH, 2),
        "economia_rs": round(kwh["solar"] * TARIFA_REDE_R_POR_KWH, 2),
    }
    return linhas, res


def main(saida):
    os.makedirs(saida, exist_ok=True)
    resumo = []
    for nome, p in CENARIOS.items():
        linhas, res = simular(nome, p)
        slug = nome.lower().replace(" ", "_")
        with open(os.path.join(saida, f"serie_{slug}.csv"), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(linhas[0].keys()))
            w.writeheader()
            w.writerows(linhas)
        resumo.append(res)
    with open(os.path.join(saida, "resumo_cenarios.json"), "w", encoding="utf-8") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=2)
    with open(os.path.join(saida, "resumo_cenarios.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(resumo[0].keys()))
        w.writeheader()
        w.writerows(resumo)
    for r in resumo:
        print(r)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "resultados")
