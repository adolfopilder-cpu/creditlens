"""
P.I.L.D.E.R™ – Módulo de Análise Detalhada
Integra: balanço completo + parecer IA + sinais RJ + relatório executivo
"""
from __future__ import annotations
import datetime as dt
import re
import os
from typing import Any, Dict, List, Optional, Tuple

ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")


# =============================================================================
# ANÁLISE DE BALANÇO DETALHADA
# =============================================================================
def extrair_numero(texto: str, padrao: str) -> Optional[float]:
    """Extrai número próximo a um padrão textual."""
    try:
        matches = re.findall(
            rf"{padrao}[^\d\n]{{0,30}}([\d\.,]+)",
            texto, re.IGNORECASE
        )
        if matches:
            v = matches[0].replace(".", "").replace(",", ".")
            return float(v)
    except Exception:
        pass
    return None


def analisar_balanco_detalhado(texto: str) -> dict:
    """
    Análise completa de balanço/DRE/balancete.
    Extrai indicadores, classifica risco e gera parecer por bloco.
    """
    if not texto or len(texto.strip()) < 50:
        return {
            "disponivel": False,
            "status": "nao_consultado",
            "resumo": "Sem demonstrações financeiras anexadas.",
            "pontos": -8,
            "indicadores": {},
            "blocos": {},
            "sinais_rj": [],
            "alertas": [],
            "positivos": [],
            "parecer": "Análise financeira não realizada por ausência de demonstrações. Avaliação conservadora aplicada.",
        }

    t = texto.lower()
    indicadores = {}
    alertas = []
    positivos = []
    sinais_rj = []
    pts = 0

    # ── BLOCO LIQUIDEZ ────────────────────────────────────────────────────
    liq_corrente = extrair_numero(texto, r"liquidez corrente")
    liq_seca = extrair_numero(texto, r"liquidez seca")
    liq_imediata = extrair_numero(texto, r"liquidez imediata")

    bloco_liquidez = {"status": "nao_consultado", "comentario": "Índices não localizados no documento."}
    if liq_corrente is not None:
        indicadores["liquidez_corrente"] = liq_corrente
        if liq_corrente >= 1.5:
            bloco_liquidez = {"status": "confirmacao", "valor": liq_corrente,
                              "comentario": f"Liquidez corrente saudável ({liq_corrente:.2f}). Boa capacidade de honrar obrigações de curto prazo."}
            positivos.append(f"Liquidez corrente saudável: {liq_corrente:.2f}")
            pts += 8
        elif liq_corrente >= 1.0:
            bloco_liquidez = {"status": "indicio", "valor": liq_corrente,
                              "comentario": f"Liquidez corrente aceitável ({liq_corrente:.2f}), mas próxima do limite mínimo. Monitorar."}
            positivos.append(f"Liquidez corrente aceitável: {liq_corrente:.2f}")
            pts += 3
        else:
            bloco_liquidez = {"status": "erro", "valor": liq_corrente,
                              "comentario": f"Liquidez corrente pressionada ({liq_corrente:.2f}). Risco de dificuldade no pagamento de obrigações correntes."}
            alertas.append(f"Liquidez corrente abaixo de 1,0: {liq_corrente:.2f}")
            sinais_rj.append("Liquidez corrente comprimida — sinal de stress de caixa")
            pts -= 12

    if liq_seca is not None:
        indicadores["liquidez_seca"] = liq_seca
        bloco_liquidez["liquidez_seca"] = liq_seca

    # ── BLOCO ENDIVIDAMENTO ───────────────────────────────────────────────
    endividamento = extrair_numero(texto, r"endividamento")
    alavancagem = extrair_numero(texto, r"alavancagem")

    bloco_endividamento = {"status": "nao_consultado", "comentario": "Índice não localizado."}
    if endividamento is not None:
        indicadores["endividamento"] = endividamento
        if endividamento <= 0.4:
            bloco_endividamento = {"status": "confirmacao", "valor": endividamento,
                                   "comentario": f"Endividamento controlado ({endividamento:.1%}). Estrutura de capital saudável."}
            positivos.append(f"Endividamento baixo: {endividamento:.1%}")
            pts += 5
        elif endividamento <= 0.7:
            bloco_endividamento = {"status": "indicio", "valor": endividamento,
                                   "comentario": f"Endividamento moderado ({endividamento:.1%}). Acompanhar evolução."}
            pts -= 3
        else:
            bloco_endividamento = {"status": "erro", "valor": endividamento,
                                   "comentario": f"Endividamento elevado ({endividamento:.1%}). Empresa altamente alavancada, risco relevante."}
            alertas.append(f"Endividamento elevado: {endividamento:.1%}")
            sinais_rj.append("Endividamento acima de 70% — risco de insolvência")
            pts -= 10

    # ── BLOCO RENTABILIDADE ───────────────────────────────────────────────
    margem_liquida = extrair_numero(texto, r"margem l[íi]quida")
    margem_ebitda = extrair_numero(texto, r"margem ebitda")
    ebitda = extrair_numero(texto, r"ebitda")
    roi = extrair_numero(texto, r"roi|retorno sobre")

    bloco_rentabilidade = {"status": "nao_consultado", "comentario": "Indicadores não localizados."}
    if margem_liquida is not None:
        indicadores["margem_liquida"] = margem_liquida
        if margem_liquida < 0:
            bloco_rentabilidade = {"status": "erro", "valor": margem_liquida,
                                   "comentario": f"Margem líquida negativa ({margem_liquida:.1%}). Empresa operando com prejuízo líquido."}
            alertas.append(f"Margem líquida negativa: {margem_liquida:.1%}")
            sinais_rj.append("Resultado líquido negativo — deterioração da rentabilidade")
            pts -= 10
        elif margem_liquida < 0.03:
            bloco_rentabilidade = {"status": "indicio", "valor": margem_liquida,
                                   "comentario": f"Margem líquida apertada ({margem_liquida:.1%}). Pouca folga para absorver variações de custo."}
            alertas.append(f"Margem líquida apertada: {margem_liquida:.1%}")
            pts -= 4
        else:
            bloco_rentabilidade = {"status": "confirmacao", "valor": margem_liquida,
                                   "comentario": f"Margem líquida positiva ({margem_liquida:.1%}). Empresa lucrativa."}
            positivos.append(f"Margem líquida positiva: {margem_liquida:.1%}")
            pts += 4

    if ebitda is not None:
        indicadores["ebitda"] = ebitda
        bloco_rentabilidade["ebitda"] = ebitda
    if margem_ebitda is not None:
        indicadores["margem_ebitda"] = margem_ebitda
        bloco_rentabilidade["margem_ebitda"] = margem_ebitda

    # ── BLOCO FLUXO DE CAIXA ─────────────────────────────────────────────
    bloco_caixa = {"status": "nao_consultado", "comentario": "Informações de fluxo de caixa não localizadas."}
    fc_negativo = any(p in t for p in [
        "fluxo de caixa negativo", "caixa negativo", "deficit de caixa",
        "queima de caixa", "cash burn"
    ])
    fc_positivo = any(p in t for p in [
        "fluxo de caixa positivo", "geração de caixa", "caixa cresceu",
        "aumento de caixa", "cash generation"
    ])

    if fc_negativo:
        bloco_caixa = {"status": "erro",
                       "comentario": "Fluxo de caixa negativo identificado. Risco de dificuldade operacional."}
        alertas.append("Fluxo de caixa negativo recorrente")
        sinais_rj.append("Consumo de caixa operacional — sinal crítico de stress")
        pts -= 14
    elif fc_positivo:
        bloco_caixa = {"status": "confirmacao",
                       "comentario": "Geração de caixa positiva identificada. Empresa com capacidade de autofinanciamento."}
        positivos.append("Geração de caixa positiva")
        pts += 6

    # ── BLOCO PATRIMÔNIO LÍQUIDO ──────────────────────────────────────────
    bloco_pl = {"status": "nao_consultado", "comentario": "PL não localizado no documento."}
    pl_negativo = any(p in t for p in [
        "patrimônio líquido negativo", "pl negativo", "passivo a descoberto",
        "capital negativo", "patrimônio negativo"
    ])
    if pl_negativo:
        bloco_pl = {"status": "erro",
                    "comentario": "Patrimônio líquido negativo (passivo a descoberto). Situação crítica de insolvência técnica."}
        alertas.append("Patrimônio líquido negativo — passivo a descoberto")
        sinais_rj.append("PL negativo — insolvência técnica identificada")
        pts -= 20

    # ── BLOCO AUDITORIA ───────────────────────────────────────────────────
    bloco_auditoria = {"status": "nao_consultado", "comentario": "Informação de auditoria não localizada."}
    if "ressalva" in t or "opinião com ressalva" in t:
        bloco_auditoria = {"status": "indicio",
                           "comentario": "Ressalva de auditoria identificada. Verificar natureza e materialidade."}
        alertas.append("Ressalva de auditoria identificada")
        pts -= 8
    elif "auditoria independente" in t or "sem ressalva" in t or "opinião não modificada" in t:
        bloco_auditoria = {"status": "confirmacao",
                           "comentario": "Auditoria independente sem ressalvas identificada."}
        positivos.append("Balanço auditado sem ressalvas")
        pts += 5

    # ── BLOCO TENDÊNCIA ───────────────────────────────────────────────────
    bloco_tendencia = {"status": "nao_consultado", "comentario": "Tendência não analisável sem série histórica."}
    crescimento = any(p in t for p in ["crescimento de receita", "aumento de receita", "receita cresceu"])
    queda = any(p in t for p in ["queda de receita", "redução de receita", "receita caiu", "retração"])
    if crescimento:
        bloco_tendencia = {"status": "confirmacao",
                           "comentario": "Tendência de crescimento de receita identificada."}
        positivos.append("Crescimento de receita em evidência")
        pts += 4
    elif queda:
        bloco_tendencia = {"status": "erro",
                           "comentario": "Queda de receita identificada. Monitorar continuidade operacional."}
        alertas.append("Queda de receita identificada")
        sinais_rj.append("Redução de receita — risco de continuidade")
        pts -= 8

    # ── BLOCO RJ / STRESS ─────────────────────────────────────────────────
    if "recuperação judicial" in t:
        alertas.append("RECUPERAÇÃO JUDICIAL mencionada no documento financeiro")
        sinais_rj.append("Recuperação Judicial mencionada em documento da empresa")
        pts -= 45

    if "concordata" in t:
        alertas.append("Concordata mencionada no documento")
        sinais_rj.append("Concordata mencionada")
        pts -= 30

    # ── RESUMO FINAL ──────────────────────────────────────────────────────
    status_geral = "confirmacao" if not alertas else "indicio" if len(alertas) <= 2 else "erro"
    resumo = ""
    if alertas:
        resumo = "⚠ " + " | ".join(alertas[:3])
    if positivos and not resumo:
        resumo = "✓ " + " | ".join(positivos[:3])
    if not resumo:
        resumo = "Balanço analisado — sem sinais críticos detectados na leitura heurística"

    parecer = _gerar_parecer_balanco(alertas, positivos, sinais_rj, indicadores)

    return {
        "disponivel": True,
        "status": status_geral,
        "resumo": resumo,
        "pontos": int(round(max(-45, min(20, pts)))),
        "indicadores": indicadores,
        "blocos": {
            "liquidez": bloco_liquidez,
            "endividamento": bloco_endividamento,
            "rentabilidade": bloco_rentabilidade,
            "fluxo_caixa": bloco_caixa,
            "patrimonio_liquido": bloco_pl,
            "auditoria": bloco_auditoria,
            "tendencia": bloco_tendencia,
        },
        "sinais_rj": sinais_rj,
        "alertas": alertas,
        "positivos": positivos,
        "parecer": parecer,
    }


def _gerar_parecer_balanco(alertas, positivos, sinais_rj, indicadores) -> str:
    partes = []
    if sinais_rj:
        partes.append(f"ATENÇÃO: {len(sinais_rj)} sinal(is) de stress financeiro identificado(s): "
                      f"{'; '.join(sinais_rj[:3])}.")
    if alertas:
        partes.append(f"Pontos de atenção: {'; '.join(alertas[:4])}.")
    if positivos:
        partes.append(f"Aspectos positivos: {'; '.join(positivos[:3])}.")
    lc = indicadores.get("liquidez_corrente")
    ml = indicadores.get("margem_liquida")
    end = indicadores.get("endividamento")
    if lc and ml and end:
        if lc >= 1.5 and ml > 0 and end <= 0.5:
            partes.append("Perfil financeiro equilibrado. Aprovação com condições padrão recomendada.")
        elif lc < 1.0 or ml < 0:
            partes.append("Perfil financeiro pressionado. Aprovação condicionada a garantias adicionais ou limite reduzido.")
    if not partes:
        partes.append("Análise heurística concluída. Revisão manual do documento original recomendada.")
    return " ".join(partes)


# =============================================================================
# ANÁLISE DE FICHA CISP DETALHADA
# =============================================================================
def analisar_cisp_detalhado(texto: str) -> dict:
    """Análise completa de ficha CISP / cadastro interno."""
    if not texto or len(texto.strip()) < 30:
        return {
            "disponivel": False,
            "status": "nao_consultado",
            "resumo": "Ficha CISP não anexada.",
            "pontos": 0,
            "historico": {},
            "comportamento": {},
            "sinais_rj": [],
            "alertas": [],
            "positivos": [],
            "parecer": "Sem ficha CISP para análise de comportamento interno.",
        }

    t = texto.lower()
    alertas = []
    positivos = []
    sinais_rj = []
    pts = 0
    historico = {}
    comportamento = {}

    # Histórico de pagamento
    if any(p in t for p in ["inadimplente", "em atraso", "vencido", "atraso recorrente"]):
        alertas.append("Histórico de inadimplência na ficha CISP")
        sinais_rj.append("Comportamento de pagamento negativo na carteira interna")
        pts -= 12
        historico["pagamento"] = "negativo"
    elif any(p in t for p in ["bom pagador", "adimplente", "pontual", "em dia"]):
        positivos.append("Histórico positivo de pagamento")
        pts += 8
        historico["pagamento"] = "positivo"

    # Concentração e aging
    aging_alto = any(p in t for p in ["acima de 60 dias", "acima de 90 dias", "> 60", "> 90"])
    if aging_alto:
        alertas.append("Aging elevado identificado na ficha")
        pts -= 6
        comportamento["aging"] = "elevado"

    # Limite e aprovações anteriores
    if any(p in t for p in ["limite aprovado", "crédito aprovado", "limite concedido"]):
        positivos.append("Crédito aprovado anteriormente")
        pts += 3
        historico["limite_anterior"] = True

    # Status do cadastro
    if any(p in t for p in ["bloqueado", "suspenso", "restrito", "negativado"]):
        alertas.append("Cadastro com restrição ativa")
        sinais_rj.append("Restrição interna ativa no cadastro")
        pts -= 15

    # Garantias e avais
    if "garantia" in t or "aval" in t or "fiador" in t:
        positivos.append("Garantia ou aval registrado na ficha")
        pts += 4
        comportamento["garantia"] = True

    # Concentração de risco
    if "concentração" in t and any(p in t for p in ["alta", "elevada", "excessiva"]):
        alertas.append("Alta concentração de risco na carteira")
        pts -= 5

    # Recorrência comercial
    if any(p in t for p in ["cliente recorrente", "relacionamento longo", "anos de relacionamento"]):
        positivos.append("Relacionamento comercial de longo prazo")
        pts += 5

    status = "confirmacao" if not alertas else "indicio" if len(alertas) <= 1 else "erro"
    resumo = (" | ".join(alertas) if alertas else "") + \
             (" | ".join(positivos) if positivos else "")
    if not resumo:
        resumo = "Ficha CISP analisada sem sinais críticos."

    parecer_cisp = "Comportamento interno: "
    if alertas:
        parecer_cisp += f"Atenção a {len(alertas)} ponto(s): {'; '.join(alertas[:2])}. "
    if positivos:
        parecer_cisp += f"Pontos positivos: {'; '.join(positivos[:2])}. "
    parecer_cisp += "Revisão do histórico completo recomendada antes da decisão."

    return {
        "disponivel": True,
        "status": status,
        "resumo": resumo,
        "pontos": int(round(max(-20, min(15, pts)))),
        "historico": historico,
        "comportamento": comportamento,
        "sinais_rj": sinais_rj,
        "alertas": alertas,
        "positivos": positivos,
        "parecer": parecer_cisp,
    }


# =============================================================================
# SINAIS DE RECUPERAÇÃO JUDICIAL / STRESS — 10 sinais clássicos
# =============================================================================
def avaliar_sinais_rj(fontes: list, balanco: dict, cisp: dict, receita: dict) -> dict:
    """
    Avalia os 10 sinais clássicos de RJ/stress financeiro.
    Classifica cada sinal: baixo | medio | alto
    """
    sinais = {}

    # 1. Queda consistente de receita
    rj1 = "nao_identificado"
    bal_sinais = balanco.get("sinais_rj", [])
    if any("receita" in s.lower() for s in bal_sinais):
        rj1 = "alto"
    elif any("receita" in str(f.get("resumo","")).lower() and "queda" in str(f.get("resumo","")).lower() for f in fontes):
        rj1 = "medio"
    sinais["queda_receita"] = {"sinal": "Queda consistente de receita", "intensidade": rj1}

    # 2. Aumento de endividamento
    end = balanco.get("indicadores", {}).get("endividamento")
    rj2 = "alto" if end and end > 0.7 else "medio" if end and end > 0.5 else "baixo" if end else "nao_identificado"
    sinais["aumento_endividamento"] = {"sinal": "Aumento de endividamento", "intensidade": rj2}

    # 3. Atrasos recorrentes
    rj3 = "nao_identificado"
    cisp_sinais = cisp.get("sinais_rj", [])
    if cisp_sinais:
        rj3 = "alto" if len(cisp_sinais) >= 2 else "medio"
    sinais["atrasos_recorrentes"] = {"sinal": "Atrasos recorrentes no pagamento", "intensidade": rj3}

    # 4. Crescimento de ações judiciais
    rj4 = "nao_identificado"
    for f in fontes:
        if "datajud" in f.get("fonte", "").lower() or "judicial" in f.get("fonte", "").lower():
            raw = f.get("raw", {})
            total = raw.get("total", 0) if raw else 0
            exec_ = raw.get("execucoes", 0) if raw else 0
            if raw.get("rj"):
                rj4 = "alto"
            elif exec_ >= 10:
                rj4 = "alto"
            elif exec_ >= 3:
                rj4 = "medio"
            elif total > 0:
                rj4 = "baixo"
    sinais["crescimento_acoes"] = {"sinal": "Crescimento de ações judiciais / execuções", "intensidade": rj4}

    # 5. Dívidas fiscais
    rj5 = "nao_identificado"
    for f in fontes:
        if "pgfn" in f.get("fonte", "").lower() or "fiscal" in f.get("fonte", "").lower():
            if f.get("status") == "confirmacao" and "listada" in f.get("resumo", "").lower():
                rj5 = "alto"
            elif f.get("pontos", 0) < -10:
                rj5 = "medio"
    sinais["dividas_fiscais"] = {"sinal": "Dívidas fiscais / PGFN", "intensidade": rj5}

    # 6. Liquidez pressionada
    lc = balanco.get("indicadores", {}).get("liquidez_corrente")
    rj6 = "alto" if lc and lc < 0.8 else "medio" if lc and lc < 1.0 else "baixo" if lc else "nao_identificado"
    sinais["liquidez_pressionada"] = {"sinal": "Liquidez corrente comprimida", "intensidade": rj6}

    # 7. Margem negativa
    ml = balanco.get("indicadores", {}).get("margem_liquida")
    rj7 = "alto" if ml is not None and ml < 0 else "medio" if ml is not None and ml < 0.02 else "nao_identificado"
    sinais["margem_negativa"] = {"sinal": "Margem líquida negativa ou muito apertada", "intensidade": rj7}

    # 8. PL negativo
    rj8 = "alto" if any("pl negativo" in s.lower() or "patrimônio" in s.lower() for s in bal_sinais) else "nao_identificado"
    sinais["pl_negativo"] = {"sinal": "Patrimônio líquido negativo", "intensidade": rj8}

    # 9. Recuperação judicial explícita
    rj9 = "nao_identificado"
    for f in fontes:
        if "recupera" in str(f.get("resumo","")).lower():
            rj9 = "alto"
            break
    if any("recupera" in s.lower() for s in bal_sinais + cisp_sinais):
        rj9 = "alto"
    sinais["recuperacao_judicial"] = {"sinal": "Recuperação Judicial / Extrajudicial", "intensidade": rj9}

    # 10. Reputação negativa ou crise
    rj10 = "nao_identificado"
    for f in fontes:
        if "reputação" in f.get("fonte", "").lower() or "mídia" in f.get("fonte", "").lower():
            if f.get("pontos", 0) <= -8:
                rj10 = "alto"
            elif f.get("pontos", 0) < 0:
                rj10 = "medio"
    sinais["reputacao_critica"] = {"sinal": "Crise reputacional ou notícias negativas", "intensidade": rj10}

    # Resumo geral
    altos = [k for k, v in sinais.items() if v["intensidade"] == "alto"]
    medios = [k for k, v in sinais.items() if v["intensidade"] == "medio"]
    nivel_geral = "critico" if len(altos) >= 3 else "alto" if len(altos) >= 1 else "medio" if len(medios) >= 2 else "baixo"

    return {
        "sinais": sinais,
        "total_altos": len(altos),
        "total_medios": len(medios),
        "nivel_geral": nivel_geral,
        "resumo": f"{len(altos)} sinal(is) ALTO + {len(medios)} MÉDIO de {len(sinais)} avaliados",
    }


# =============================================================================
# PARECER EXECUTIVO VIA CLAUDE API
# =============================================================================
def gerar_parecer_ia(resultado: dict, balanco: dict, cisp: dict) -> str:
    """Gera parecer executivo usando Claude API."""
    if not ANTHROPIC_API_KEY:
        return _parecer_regras(resultado, balanco, cisp)

    try:
        import urllib.request, json as _json

        empresa = resultado.get("empresa", "")
        score = resultado.get("score", 0)
        rating = resultado.get("rating", "")
        risco = resultado.get("classificacao_risco", "")
        pd_val = resultado.get("pd", 0)
        red_flags = resultado.get("red_flags", [])
        yellow_flags = resultado.get("yellow_flags", [])
        green_flags = resultado.get("green_flags", [])
        sinais_rj = resultado.get("sinais_rj", [])
        fontes_ok = resultado.get("fontes_consultadas", 0)
        total_fontes = resultado.get("total_fontes", 0)

        bal_resumo = balanco.get("resumo", "Não disponível")
        bal_parecer = balanco.get("parecer", "")
        cisp_resumo = cisp.get("resumo", "Não disponível")
        indicadores = balanco.get("indicadores", {})

        prompt = f"""Você é um Gestor de Crédito Sênior brasileiro com 20 anos de experiência.
Assine como: {ASSINATURA}

Analise os dados abaixo e produza um PARECER EXECUTIVO DE CRÉDITO completo:

EMPRESA: {empresa}
SCORE: {score}/100 | RATING: {rating} | RISCO: {risco} | PD: {pd_val}%
FONTES CONSULTADAS: {fontes_ok}/{total_fontes}

RED FLAGS ({len(red_flags)}): {'; '.join(red_flags[:5]) if red_flags else 'Nenhum'}
YELLOW FLAGS ({len(yellow_flags)}): {'; '.join(yellow_flags[:5]) if yellow_flags else 'Nenhum'}
GREEN FLAGS ({len(green_flags)}): {'; '.join(green_flags[:5]) if green_flags else 'Nenhum'}
SINAIS RJ ({len(sinais_rj)}): {'; '.join(sinais_rj[:5]) if sinais_rj else 'Nenhum'}

BALANÇO: {bal_resumo}
Indicadores: {_json.dumps(indicadores, ensure_ascii=False)}

COMPORTAMENTO INTERNO (CISP): {cisp_resumo}

Produza:

1. LEITURA DO ANALISTA (4-5 bullets assertivos, linguagem de gestor financeiro sênior)
2. DECISÃO RECOMENDADA (Aprovar / Aprovar com restrições / Negar — com justificativa objetiva)
3. CONDIÇÕES E GARANTIAS SUGERIDAS (se aprovado)
4. PLANO DE MONITORAMENTO (frequência e gatilhos)
5. NÍVEL DE RISCO CONSOLIDADO (baixo / médio / alto / crítico)

Seja direto, técnico e assertivo. Máximo 300 palavras.
Inicie com: P.I.L.D.E.R™ — Parecer Executivo de Crédito"""

        payload = _json.dumps({
            "model": "claude-sonnet-4-20250514",
            "max_tokens": 600,
            "messages": [{"role": "user", "content": prompt}]
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
            }
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = _json.loads(resp.read())
            return data["content"][0]["text"]

    except Exception as e:
        return _parecer_regras(resultado, balanco, cisp)


def _parecer_regras(resultado: dict, balanco: dict, cisp: dict) -> str:
    """Parecer baseado em regras quando API não disponível."""
    score = resultado.get("score", 0)
    rating = resultado.get("rating", "")
    red_flags = resultado.get("red_flags", [])
    sinais_rj = resultado.get("sinais_rj", [])
    lc = balanco.get("indicadores", {}).get("liquidez_corrente")
    ml = balanco.get("indicadores", {}).get("margem_liquida")

    partes = [f"{ASSINATURA} — Parecer Executivo (Baseado em Regras)\n"]

    if sinais_rj or rating in ("D", "C"):
        partes.append("DECISÃO: NEGAR ou condicionar a garantia real.")
        partes.append(f"Justificativa: {len(sinais_rj)} sinal(is) de stress/RJ identificado(s). Rating {rating} indica risco elevado.")
        partes.append("Condições mínimas para reconsideração: laudo jurídico, certidão negativa de RJ, garantia real formalizada.")
        partes.append("Monitoramento: semanal com gatilho imediato de bloqueio.")
    elif rating in ("BB", "B") or len(red_flags) >= 2:
        partes.append("DECISÃO: APROVAR COM RESTRIÇÕES.")
        partes.append(f"Justificativa: Rating {rating} com {len(red_flags)} red flag(s). Risco moderado-alto.")
        partes.append("Condições: limite reduzido (50-70% do padrão), prazo 7-14 dias, aval dos sócios.")
        partes.append("Monitoramento: mensal com revisão trimestral do limite.")
    elif rating in ("BBB", "A"):
        partes.append("DECISÃO: APROVAR COM MONITORAMENTO.")
        partes.append(f"Justificativa: Rating {rating}. Perfil de risco médio controlado.")
        partes.append("Condições: limite padrão, prazo 14-28 dias, certidões atualizadas.")
        partes.append("Monitoramento: trimestral com gatilho mensal para mudanças fiscais/judiciais.")
    else:
        partes.append("DECISÃO: APROVAR.")
        partes.append(f"Justificativa: Rating {rating}. Perfil de risco baixo.")
        partes.append("Condições: limite conforme política interna, prazo 28-35 dias.")
        partes.append("Monitoramento: semestral.")

    if lc:
        partes.append(f"Liquidez corrente: {lc:.2f} — {'adequada' if lc >= 1.0 else 'pressionada — atenção ao caixa'}.")
    if ml is not None:
        partes.append(f"Margem líquida: {ml:.1%} — {'positiva' if ml >= 0 else 'negativa — resultado operacional comprometido'}.")

    return "\n".join(partes)


# =============================================================================
# RELATÓRIO EXECUTIVO CONSOLIDADO
# =============================================================================
def gerar_relatorio_completo(resultado: dict, balanco: dict, cisp: dict) -> dict:
    """
    Consolida tudo em um único objeto de relatório completo.
    Usado pelo endpoint /api/analisar-completo
    """
    sinais_rj_avaliados = avaliar_sinais_rj(
        resultado.get("fontes", []), balanco, cisp,
        resultado.get("dados", {}).get("receita", {})
    )
    parecer_ia = gerar_parecer_ia(resultado, balanco, cisp)

    return {
        **resultado,
        "balanco_detalhado": balanco,
        "cisp_detalhado": cisp,
        "sinais_rj_avaliados": sinais_rj_avaliados,
        "parecer_executivo": parecer_ia,
        "assinatura": ASSINATURA,
        "relatorio_gerado_em": dt.datetime.now().isoformat(),
    }
