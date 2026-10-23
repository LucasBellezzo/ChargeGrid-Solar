# Sprint 3 (SERS + PCAP) - Controle de recarga com solar via LDR, outras
# cargas via potenciometro, rele como saida real e botao pra sessao.
# Obs: a parte de COA (decimal/binario/hex) foi entregue separado pelo grupo.

import time
from machine import Pin, ADC

ledVerde = Pin(3, Pin.OUT)      # recarga 100% solar
ledAmarelo = Pin(2, Pin.OUT)    # recarga completa (solar + rede, ou so rede)
ledVermelho = Pin(1, Pin.OUT)   # recarga reduzida (nao da pra entregar a demanda toda)

releEnergia = Pin(4, Pin.OUT)          # liga/desliga a entrega de energia de verdade
botaoSessao = Pin(5, Pin.IN, Pin.PULL_UP)  # aperta pra iniciar/parar a sessao

adcLdr = ADC(Pin(27))     # LDR, representa a geracao solar
adcCarga = ADC(Pin(26))   # potenciometro, representa a carga de outras estacoes

GERACAO_MAX_W = 4000                # geracao solar maxima que o LDR pode representar
CARGA_MAX_OUTRAS_ESTACOES_W = 3000  # carga maxima que o potenciometro pode representar
DEMANDA_RECARGA_W = 3000            # quanto o carregador tenta entregar pro carro
CAPACIDADE_REDE_MAX_W = 3500        # quanto o posto pode puxar da rede (sozinha ja cobre a demanda)

INTERVALO_LOOP_S = 2


# le o LDR e converte pra uma faixa de Watts (mais luz = mais geracao)
def lerGeracaoSolar():
    leitura = adcLdr.read_u16()
    return round((leitura / 65535) * GERACAO_MAX_W)


# le o potenciometro e converte pra Watts (carga de outras estacoes do posto)
def lerCargaOutrasEstacoes():
    leitura = adcCarga.read_u16()
    return round((leitura / 65535) * CARGA_MAX_OUTRAS_ESTACOES_W)


# detecta o clique no botao (quando ele e solto depois de pressionado)
def lerBotaoSessao(estavaPressionado):
    pressionadoAgora = (botaoSessao.value() == 0)
    clique = estavaPressionado and not pressionadoAgora
    return clique, pressionadoAgora


# calcula quanto vem do solar e quanto vem da rede, e decide o estado
def calcularFornecimento(geracaoSolar, cargaOutrasEstacoes):
    # outras estacoes consomem da capacidade TOTAL do posto (solar + rede),
    # nao so do solar -- assim a rede sozinha tambem pode ficar sobrecarregada
    capacidadeTotal = geracaoSolar + CAPACIDADE_REDE_MAX_W
    sobraParaRecarga = max(0, capacidadeTotal - cargaOutrasEstacoes)
    entrega = min(DEMANDA_RECARGA_W, sobraParaRecarga)

    # o solar e "gasto" primeiro; o que sobrar da demanda vem da rede
    solarRestante = max(0, geracaoSolar - cargaOutrasEstacoes)
    entregaSolar = min(entrega, solarRestante)
    entregaRede = entrega - entregaSolar

    if entrega < DEMANDA_RECARGA_W:
        estado = "RECARGA REDUZIDA (POTENCIA LIMITADA)"
    elif entregaRede == 0:
        estado = "RECARGA 100% SOLAR"
    else:
        estado = "RECARGA COMPLETA (SOLAR+REDE)"

    return {"estado": estado, "solar": entregaSolar, "rede": entregaRede}


# acende o LED do estado atual e apaga os outros
def atualizarLeds(estado):
    ledVerde.off()
    ledAmarelo.off()
    ledVermelho.off()

    if estado == "RECARGA 100% SOLAR":
        ledVerde.on()
    elif estado == "RECARGA COMPLETA (SOLAR+REDE)":
        ledAmarelo.on()
    else:
        ledVermelho.on()


# libera energia (mesmo reduzida) sempre que tiver sessao ativa e sobrar algo pra entregar
def atualizarRele(dadosCarga, sessaoAtiva):
    entregaTotal = dadosCarga["solar"] + dadosCarga["rede"]
    liberar = sessaoAtiva and entregaTotal > 0
    releEnergia.value(1 if liberar else 0)
    return liberar


# mostra os dados no serial
def exibirStatus(dadosCarga, sessaoAtiva, tempoSessao, energiaSessao, releLigado):
    total = dadosCarga["solar"] + dadosCarga["rede"]
    pctSolar = round((dadosCarga["solar"] / total) * 100) if total > 0 else 0

    print("=" * 50)
    print(f"STATUS: {dadosCarga['estado']}")
    print(f"SOLAR: {dadosCarga['solar']}W   REDE: {dadosCarga['rede']}W   % SOLAR: {pctSolar}%")
    print(f"SESSAO: {'ATIVA' if sessaoAtiva else 'PARADA'}   RELE: {'LIGADO' if releLigado else 'DESLIGADO'}")
    if sessaoAtiva:
        print(f"TEMPO DE SESSAO: {tempoSessao}s   ENERGIA ENTREGUE: {round(energiaSessao, 2)}Wh")
    print("=" * 50)


# loop principal: le os sensores, decide o estado e atualiza tudo, sem parar
def executarAutomacao():
    sessaoAtiva = False
    tempoSessao = 0
    energiaSessao = 0.0
    botaoPressionado = False

    while True:
        clique, botaoPressionado = lerBotaoSessao(botaoPressionado)
        if clique:
            sessaoAtiva = not sessaoAtiva
            tempoSessao = 0
            energiaSessao = 0.0
            print(f"[EVENTO] Sessao {'iniciada' if sessaoAtiva else 'encerrada'}.")

        geracaoSolar = lerGeracaoSolar()
        cargaOutrasEstacoes = lerCargaOutrasEstacoes()

        dadosCarga = calcularFornecimento(geracaoSolar, cargaOutrasEstacoes)
        atualizarLeds(dadosCarga["estado"])
        releLigado = atualizarRele(dadosCarga, sessaoAtiva)

        if sessaoAtiva and releLigado:
            tempoSessao += INTERVALO_LOOP_S
            potenciaEntregue = dadosCarga["solar"] + dadosCarga["rede"]
            energiaSessao += potenciaEntregue * (INTERVALO_LOOP_S / 3600)

        exibirStatus(dadosCarga, sessaoAtiva, tempoSessao, energiaSessao, releLigado)
        time.sleep(INTERVALO_LOOP_S)


executarAutomacao()
