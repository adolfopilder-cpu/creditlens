"""
P.I.L.D.E.R™ – Módulo de Análise Detalhada v2.0
Framework: CONFIRMAÇÃO | EVIDÊNCIA | INDÍCIO | AUSÊNCIA
Nível de confiança por bloco: Alto | Médio | Baixo
Rastreabilidade completa por consulta
"""
from __future__ import annotations
import datetime as dt
import re
import os
import json
import urllib.request
from typing import Any, Dict, List, Optional

ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"

# =============================================================================
# FRAMEWORK DE EVIDÊNCIA — CONFIRMAÇÃO | EVIDÊNCIA | INDÍCIO | AUSÊNCIA
# =============================================================================
CATEGORIAS_EVIDENCIA = {
    "CONFIRMACAO": {
        "label": "CONFIRMAÇÃO",
        "descricao": "Evidência direta em fonte primária ou oficial",
        "confianca": "Alto",
        "cor": "#0e7a5a",
        "icone": "✅"
    },
    "EVIDENCIA": {
        "label": "EVIDÊNCIA",
        "descricao": "Forte suporte em fonte confiável, mas não primária",
        "confianca": "Alto",
        "cor": "#16a34a",
        "icone": "🟢"
    },
    "INDICIO": {
        "label": "INDÍCIO",
        "descricao": "Probabilidade relevante, sem prova conclusiva",
        "confianca": "Médio",
        "cor": "#b45309",
        "icone": "🟡"
    },
    "AUSENCIA": {
        "label": "AUSÊNCIA",
        "descricao": "Dado não encontrado ou não acessível — NUNCA equivale a regularidade",
        "confianca": "Baixo",
        "cor": "#6b7280",
        "icone": "⚪"
    },
    "ALERTA": {
        "label": "ALERTA",
        "descricao": "Evidência negativa confirmada",
        "confianca": "Alto",
        "cor": "#c0392b",
        "icone": "🔴"
    }
}

def classificar_evidencia_fonte(fonte: dict) -> str:
    """Classifica uma fonte no framework de evidência."""
    status = fonte.get("status", "")
    pontos = fonte.get("pontos", 0)
    if status == "confirmacao" and pontos > 0:
        return "CONFIRMACAO"
    elif status == "confirmacao" and pontos <= -10:
        return "ALERTA"
    elif status in ("evidencia", "confirmacao"):
        return "EVIDENCIA"
    elif status == "indicio":
        return "INDICIO"
    elif status in ("pendente", "nao_consultado", "ausencia"):
        return "AUSENCIA"
    elif status == "erro":
        return "AUSENCIA"
    return "INDICIO"

def calcular_confianca_bloco(fontes_bloco: list) -> str:
    """Calcula nível de confiança de um bloco baseado nas fontes."""
    if not fontes_bloco:
        return "Baixo"
    confirmacoes = sum(1 for f in fontes_bloco
                      if f.get("categoria_evidencia") in ("CONFIRMACAO", "EVIDENCIA", "ALERTA"))
    ausencias = sum(1 for f in fontes_bloco
                   if f.get("categoria_evidencia") == "AUSENCIA")
    total = len(fontes_bloco)
    if confirmacoes >= total * 0.7:
        return "Alto"
    elif confirmacoes >= total * 0.4:
        return "Médio"
    return "Baixo"

# =============================================================================
# PROMPT ANALISTA SÊNIOR — Framework P.I.L.D.E.R™
# =============================================================================
def montar_prompt_analista(cnpj: str, dados_cadastrais: dict,
                            dados_fontes: list, balanco_texto: str,
                            cisp_texto: str) -> str:
    """Monta o prompt completo do Analista de Crédito Sênior."""

    # Formata dados cadastrais
    cadastro_str = json.dumps({
        k: v for k, v in dados_cadastrais.items()
        if k not in ("raw", "evidence")
    }, ensure_ascii=False, indent=2)

    # Fontes já consultadas
    fontes_str = "\n".join([
        f"- [{f.get('categoria_evidencia','?')}] {f.get('fonte','')}: {f.get('resumo','')}"
        for f in dados_fontes if f.get("status") not in ("pendente",)
    ])

    bal_resumo = balanco_texto[:3000] if balanco_texto else "Não disponível"
    cisp_resumo = cisp_texto[:1500] if cisp_texto else "Não disponível"

    return f"""Atue como ANALISTA DE CRÉDITO SÊNIOR com visão de auditoria, governança e compliance (nível banco, Bacen, Big4 e indústria).

ASSINATURA OBRIGATÓRIA: {ASSINATURA}

OBJETIVO
Realizar análise de crédito completa, rastreável, auditável, estruturada e defensável do CNPJ informado.

CNPJ: {cnpj}

DADOS CADASTRAIS DISPONÍVEIS (fonte: Receita Federal via BrasilAPI):
{cadastro_str}

FONTES JÁ CONSULTADAS PELO SISTEMA P.I.L.D.E.R™:
{fontes_str}

BALANÇO / DEMONSTRAÇÕES FINANCEIRAS:
{bal_resumo}

COMPORTAMENTO INTERNO (CISP):
{cisp_resumo}

═══════════════════════════════════════════════════════════
REGRAS OBRIGATÓRIAS DE AUDITORIA E GOVERNANÇA
═══════════════════════════════════════════════════════════
1. Classifique TODA informação em uma destas categorias:
   - CONFIRMAÇÃO = evidência direta em fonte primária ou oficial
   - EVIDÊNCIA = forte suporte em fonte confiável, mas não primária
   - INDÍCIO = probabilidade relevante, sem prova conclusiva
   - AUSÊNCIA = dado não encontrado ou não acessível
2. NUNCA trate ausência como regularidade. Ausência aumenta o conservadorismo.
3. Sempre informar a fonte consultada ou o motivo da ausência.
4. Apontar inconsistências entre bases quando identificadas.
5. Diferenciar claramente: FATO | INFERÊNCIA | HIPÓTESE
6. Calcular score com memória de cálculo explícita.
7. Informar nível de confiança por bloco: Alto | Médio | Baixo
8. Se houver limitação de dados, reduzir confiança e tornar conclusão mais conservadora.
9. NÃO inventar números financeiros. Se não há dado, dizer explicitamente.
10. Se houver dados incompletos, explicitar o que falta para decisão definitiva.

═══════════════════════════════════════════════════════════
ESTRUTURA OBRIGATÓRIA DO PARECER
═══════════════════════════════════════════════════════════

## 1. IDENTIFICAÇÃO E CADASTRO
[Confiança: Alto/Médio/Baixo]
- Razão social, CNPJ, situação cadastral, tempo de mercado
- CNAE principal e risco setorial
- Quadro societário — listar sócios e participações
- Capital social
- Categoria de evidência por dado

## 2. ANÁLISE FISCAL E TRIBUTÁRIA
[Confiança: Alto/Médio/Baixo]
- PGFN / dívida ativa: [CONFIRMAÇÃO/AUSÊNCIA/INDÍCIO]
- Simples Nacional / regime tributário
- Regularidade fiscal federal e estadual
- O que falta para conclusão definitiva

## 3. ANÁLISE JUDICIAL E PROCESSUAL
[Confiança: Alto/Médio/Baixo]
- Total de processos, execuções, trabalhistas
- Recuperação judicial / extrajudicial
- Tribunais consultados
- Nível de risco jurídico

## 4. ANÁLISE DE SANÇÕES E IDONEIDADE
[Confiança: Alto/Médio/Baixo]
- CEIS / CNEP / OFAC / listas internacionais
- PEP — Pessoas Politicamente Expostas
- Resultado por lista

## 5. ANÁLISE FINANCEIRA
[Confiança: Alto/Médio/Baixo]
- Indicadores extraídos do balanço (se disponível)
- Liquidez, endividamento, margem, EBITDA, fluxo de caixa
- Se não disponível: explicitar impacto no score e o que solicitar
- Categoria de evidência: CONFIRMAÇÃO/INDÍCIO/AUSÊNCIA

## 6. COMPORTAMENTO COMERCIAL E REPUTAÇÃO
[Confiança: Alto/Médio/Baixo]
- Histórico interno (CISP)
- Notícias e mídia
- Reclame Aqui / reputação digital
- Relacionamento com a carteira

## 7. RED FLAGS — ALERTAS CRÍTICOS
Liste APENAS fatos confirmados ou com forte evidência.
Para cada red flag: fonte + categoria de evidência + impacto no score

## 8. YELLOW FLAGS — PONTOS DE ATENÇÃO
Para cada yellow flag: fonte + categoria + o que monitorar

## 9. GREEN FLAGS — ASPECTOS POSITIVOS
Para cada green flag: fonte + categoria + peso positivo

## 10. SINAIS DE RECUPERAÇÃO JUDICIAL / STRESS
Avalie os 10 sinais clássicos:
1. Queda consistente de receita
2. Compressão de margens
3. Liquidez abaixo de 1,0
4. Endividamento acima de 70%
5. Fluxo de caixa negativo recorrente
6. Crescimento de execuções judiciais
7. Dívidas fiscais relevantes
8. Patrimônio líquido negativo
9. Recuperação judicial explícita
10. Crise reputacional grave

Para cada sinal: [NÃO IDENTIFICADO / BAIXO / MÉDIO / ALTO / CRÍTICO]

## 11. MEMÓRIA DE CÁLCULO DO SCORE
Base: 50 pontos
Ajustes por bloco (com justificativa):
- Cadastral: +/- X pontos | Confiança: Alto/Médio/Baixo
- Fiscal: +/- X pontos | Confiança: Alto/Médio/Baixo
- Judicial: +/- X pontos | Confiança: Alto/Médio/Baixo
- Financeiro: +/- X pontos | Confiança: Alto/Médio/Baixo
- Reputação: +/- X pontos | Confiança: Alto/Médio/Baixo
- Setor: +/- X pontos | Confiança: Alto/Médio/Baixo
Score final: XX/100 | Rating: XX | PD: X,X%

## 12. DECISÃO RECOMENDADA
[APROVAR / APROVAR COM RESTRIÇÕES / NEGAR / AGUARDAR INFORMAÇÕES]
Justificativa objetiva baseada nos dados coletados.
Condições e garantias (se aprovado com restrições).
O que falta para decidir com maior confiança.

## 13. PLANO DE MONITORAMENTO
Frequência, gatilhos de alerta e ações por cenário.

## 14. LEITURA FINAL DO ANALISTA
4-5 bullets assertivos, linguagem de gestor financeiro sênior.
Máximo 150 palavras. Direto ao ponto.

═══════════════════════════════════════════════════════════
ASSINATURA FINAL: {ASSINATURA}
═══════════════════════════════════════════════════════════"""


# =============================================================================
# GERAR PARECER VIA CLAUDE API
# =============================================================================
def gerar_parecer_analista_senior(
    cnpj: str,
    dados_cadastrais: dict,
    fontes: list,
    balanco_texto: str = "",
    cisp_texto: str = "",
) -> dict:
    """
    Gera parecer completo via Claude API usando o PROMPT_ANALISTA sênior.
    Retorna dict com parecer, blocos e metadados.
    """
    timestamp = dt.datetime.now().isoformat()

    # Classificar evidências nas fontes
    fontes_classificadas = []
    for f in fontes:
        fc = dict(f)
        fc["categoria_evidencia"] = classificar_evidencia_fonte(f)
        fc["info_categoria"] = CATEGORIAS_EVIDENCIA.get(fc["categoria_evidencia"], {})
        fontes_classificadas.append(fc)

    # Agrupar por bloco para calcular confiança
    blocos_confianca = {
        "cadastral": calcular_confianca_bloco([f for f in fontes_classificadas
                                              if "receita" in f.get("fonte","").lower()
                                              or "simples" in f.get("fonte","").lower()]),
        "fiscal": calcular_confianca_bloco([f for f in fontes_classificadas
                                           if "pgfn" in f.get("fonte","").lower()
                                           or "fiscal" in f.get("fonte","").lower()
                                           or "fgts" in f.get("fonte","").lower()]),
        "judicial": calcular_confianca_bloco([f for f in fontes_classificadas
                                             if "judicial" in f.get("fonte","").lower()
                                             or "datajud" in f.get("fonte","").lower()]),
        "sancoes": calcular_confianca_bloco([f for f in fontes_classificadas
                                            if "ceis" in f.get("fonte","").lower()
                                            or "cnep" in f.get("fonte","").lower()
                                            or "ofac" in f.get("fonte","").lower()]),
        "financeiro": "Alto" if balanco_texto and len(balanco_texto) > 200 else "Baixo",
        "reputacao": calcular_confianca_bloco([f for f in fontes_classificadas
                                              if "reputação" in f.get("fonte","").lower()
                                              or "mídia" in f.get("fonte","").lower()]),
        "comportamento": "Alto" if cisp_texto and len(cisp_texto) > 100 else "Baixo",
    }

    # Tenta gerar parecer via Claude API
    parecer_texto = ""
    via_ia = False

    if ANTHROPIC_API_KEY:
        try:
            prompt = montar_prompt_analista(
                cnpj, dados_cadastrais, fontes_classificadas,
                balanco_texto, cisp_texto
            )
            payload = json.dumps({
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4000,
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
            with urllib.request.urlopen(req, timeout=45) as resp:
                data = json.loads(resp.read())
                parecer_texto = data["content"][0]["text"]
                via_ia = True
        except Exception as e:
            parecer_texto = _parecer_por_regras(
                cnpj, dados_cadastrais, fontes_classificadas,
                blocos_confianca, balanco_texto, cisp_texto
            )
    else:
        parecer_texto = _parecer_por_regras(
            cnpj, dados_cadastrais, fontes_classificadas,
            blocos_confianca, balanco_texto, cisp_texto
        )

    return {
        "parecer_completo": parecer_texto,
        "via_ia": via_ia,
        "fontes_classificadas": fontes_classificadas,
        "blocos_confianca": blocos_confianca,
        "framework": "CONFIRMACAO|EVIDENCIA|INDICIO|AUSENCIA",
        "gerado_em": timestamp,
        "assinatura": ASSINATURA,
        "rastreabilidade": {
            "cnpj": cnpj,
            "total_fontes": len(fontes),
            "fontes_confirmadas": len([f for f in fontes_classificadas
                                      if f.get("categoria_evidencia") in ("CONFIRMACAO","EVIDENCIA")]),
            "fontes_ausencia": len([f for f in fontes_classificadas
                                   if f.get("categoria_evidencia") == "AUSENCIA"]),
            "fontes_alerta": len([f for f in fontes_classificadas
                                 if f.get("categoria_evidencia") == "ALERTA"]),
        }
    }


def _parecer_por_regras(cnpj, cadastro, fontes, blocos_confianca,
                         balanco_texto, cisp_texto) -> str:
    """Parecer estruturado por regras quando API não disponível."""
    razao = cadastro.get("razao_social", "Não identificado")
    situacao = cadastro.get("situacao", "")
    uf = cadastro.get("uf", "")
    cnae = cadastro.get("cnae", "")
    anos = cadastro.get("anos_mercado")

    confirmacoes = [f for f in fontes if f.get("categoria_evidencia") in ("CONFIRMACAO","EVIDENCIA")]
    alertas = [f for f in fontes if f.get("categoria_evidencia") == "ALERTA"]
    ausencias = [f for f in fontes if f.get("categoria_evidencia") == "AUSENCIA"]
    indicios = [f for f in fontes if f.get("categoria_evidencia") == "INDICIO"]

    linhas = [
        f"{ASSINATURA}",
        "=" * 70,
        "PARECER EXECUTIVO DE CRÉDITO — ANALISTA SÊNIOR P.I.L.D.E.R™",
        f"(Gerado por regras — configure ANTHROPIC_API_KEY para parecer via IA)",
        "=" * 70,
        "",
        "## 1. IDENTIFICAÇÃO E CADASTRO",
        f"[Confiança: {blocos_confianca.get('cadastral','Baixo')}]",
        f"Empresa: {razao} | CNPJ: {cnpj}",
        f"Situação: {situacao} | UF: {uf} | Mercado: {f'{anos:.1f} anos' if anos else 'N/D'}",
        f"CNAE: {cnae}",
        f"Categoria: {'CONFIRMAÇÃO' if 'ativ' in situacao.lower() else 'INDÍCIO'}",
        "",
        "## 2. ANÁLISE FISCAL E TRIBUTÁRIA",
        f"[Confiança: {blocos_confianca.get('fiscal','Baixo')}]",
    ]

    fiscal_f = next((f for f in fontes if "pgfn" in f.get("fonte","").lower()), None)
    if fiscal_f:
        cat = fiscal_f.get("categoria_evidencia","AUSENCIA")
        linhas.append(f"PGFN: [{cat}] {fiscal_f.get('resumo','')}")
    else:
        linhas.append("PGFN: [AUSÊNCIA] Não consultado — ausência NÃO equivale a regularidade.")
    linhas.append("O que falta: Certidão negativa federal, FGTS/CRF, regularidade estadual.")
    linhas.append("")

    linhas.append("## 3. ANÁLISE JUDICIAL E PROCESSUAL")
    linhas.append(f"[Confiança: {blocos_confianca.get('judicial','Baixo')}]")
    jud_f = next((f for f in fontes if "judicial" in f.get("fonte","").lower()), None)
    if jud_f:
        raw = jud_f.get("raw", {})
        total = raw.get("total", 0) if raw else 0
        exec_ = raw.get("execucoes", 0) if raw else 0
        rj = raw.get("rj", False) if raw else False
        cat = jud_f.get("categoria_evidencia", "AUSENCIA")
        linhas.append(f"DataJud: [{cat}] {total} processo(s) | {exec_} execução(ões)")
        if rj:
            linhas.append("⚠ RECUPERAÇÃO JUDICIAL IDENTIFICADA — RISCO CRÍTICO")
    else:
        linhas.append("Judicial: [AUSÊNCIA] Base judicial não consultada.")
    linhas.append("")

    linhas.append("## 4. SANÇÕES E IDONEIDADE")
    linhas.append(f"[Confiança: {blocos_confianca.get('sancoes','Baixo')}]")
    for nome in ["ceis","cnep"]:
        f = next((x for x in fontes if nome in x.get("fonte","").lower()), None)
        if f:
            cat = f.get("categoria_evidencia","AUSENCIA")
            linhas.append(f"{nome.upper()}: [{cat}] {f.get('resumo','')}")
    linhas.append("")

    linhas.append("## 5. ANÁLISE FINANCEIRA")
    linhas.append(f"[Confiança: {blocos_confianca.get('financeiro','Baixo')}]")
    if balanco_texto and len(balanco_texto) > 200:
        linhas.append("[EVIDÊNCIA] Balanço/DRE analisado — ver análise detalhada de balanço.")
    else:
        linhas.append("[AUSÊNCIA] Sem demonstrações financeiras.")
        linhas.append("Impacto: penalidade conservadora aplicada (-8 pts).")
        linhas.append("O que falta: Balanço auditado, DRE, DFC dos últimos 2 exercícios.")
    linhas.append("")

    linhas.append("## 6. REPUTAÇÃO E COMPORTAMENTO")
    linhas.append(f"[Confiança: {blocos_confianca.get('reputacao','Baixo')}]")
    rep_f = next((f for f in fontes if "reputação" in f.get("fonte","").lower()
                  or "mídia" in f.get("fonte","").lower()), None)
    if rep_f:
        cat = rep_f.get("categoria_evidencia","AUSENCIA")
        linhas.append(f"Mídia/Reputação: [{cat}] {rep_f.get('resumo','')}")
    if cisp_texto and len(cisp_texto) > 50:
        linhas.append("[EVIDÊNCIA] Ficha CISP analisada — ver análise comportamental.")
    else:
        linhas.append("[AUSÊNCIA] Sem ficha CISP/comportamento interno disponível.")
    linhas.append("")

    # Red/Yellow/Green consolidados
    linhas.append("## 7-9. FLAGS CONSOLIDADOS")
    if alertas:
        linhas.append("🔴 RED FLAGS:")
        for a in alertas[:5]:
            linhas.append(f"  [{a.get('categoria_evidencia','')}] {a.get('resumo','')[:100]}")
    for f in fontes:
        if f.get("pontos",0) <= -10 and f.get("categoria_evidencia") != "ALERTA":
            linhas.append(f"  [ALERTA] {f.get('resumo','')[:100]}")

    linhas.append("🟡 YELLOW FLAGS (ausências críticas):")
    for a in ausencias[:4]:
        linhas.append(f"  [AUSÊNCIA] {a.get('fonte','')} — não consultado")

    if confirmacoes:
        linhas.append("🟢 GREEN FLAGS:")
        for c in confirmacoes[:4]:
            if c.get("pontos",0) > 0:
                linhas.append(f"  [{c.get('categoria_evidencia','')}] {c.get('resumo','')[:100]}")
    linhas.append("")

    # 10 sinais RJ
    linhas.append("## 10. SINAIS DE STRESS / RECUPERAÇÃO JUDICIAL")
    sinais = _avaliar_10_sinais(fontes, balanco_texto)
    for k, v in sinais.items():
        icone = "🔴" if v == "ALTO" or v == "CRÍTICO" else "🟡" if v == "MÉDIO" else "⚪"
        linhas.append(f"  {icone} {k}: {v}")
    linhas.append("")

    # Memória de cálculo
    linhas.append("## 11. MEMÓRIA DE CÁLCULO")
    linhas.append("Base: 50 pontos")
    for f in fontes:
        pts = f.get("pontos", 0)
        if pts != 0:
            sinal = "+" if pts > 0 else ""
            linhas.append(f"  {f.get('fonte','')[:50]}: {sinal}{pts} pts "
                          f"[{f.get('categoria_evidencia','?')}]")
    linhas.append("")

    # Decisão
    linhas.append("## 12. DECISÃO E PLANO DE MONITORAMENTO")
    alertas_criticos = [f for f in fontes if f.get("pontos",0) <= -20]
    if alertas_criticos or any(v in ("ALTO","CRÍTICO") for v in sinais.values()):
        linhas.append("DECISÃO: NEGAR ou condicionar a garantia real.")
        linhas.append("Justificativa: Sinais críticos identificados.")
        linhas.append("Monitoramento: Semanal com gatilho imediato de bloqueio.")
    elif ausencias:
        linhas.append("DECISÃO: AGUARDAR INFORMAÇÕES")
        linhas.append(f"Falta: {len(ausencias)} fonte(s) não consultada(s) — decisão incompleta.")
        linhas.append("Monitoramento: Solicitar documentação antes de aprovar.")
    else:
        linhas.append("DECISÃO: APROVAR COM RESTRIÇÕES")
        linhas.append("Condições: limite conservador, monitoramento mensal.")

    linhas.append("")
    linhas.append("=" * 70)
    linhas.append(ASSINATURA)
    linhas.append("=" * 70)

    return "\n".join(linhas)


def _avaliar_10_sinais(fontes: list, balanco_texto: str) -> dict:
    """Avalia os 10 sinais clássicos de RJ/stress."""
    t = balanco_texto.lower() if balanco_texto else ""
    jud = next((f for f in fontes if "judicial" in f.get("fonte","").lower()), {})
    raw_jud = jud.get("raw", {}) or {}

    return {
        "1. Queda de receita": "ALTO" if "queda de receita" in t or "redução de receita" in t else "NÃO IDENTIFICADO",
        "2. Compressão de margens": "ALTO" if "margem negativa" in t else "MÉDIO" if "margem apertada" in t else "NÃO IDENTIFICADO",
        "3. Liquidez < 1,0": "ALTO" if "liquidez corrente pressionada" in t or "liquidez abaixo" in t else "NÃO IDENTIFICADO",
        "4. Endividamento > 70%": "ALTO" if "endividamento elevado" in t else "NÃO IDENTIFICADO",
        "5. Fluxo de caixa negativo": "ALTO" if "fluxo de caixa negativo" in t else "NÃO IDENTIFICADO",
        "6. Execuções crescendo": "ALTO" if raw_jud.get("execucoes",0) >= 10 else "MÉDIO" if raw_jud.get("execucoes",0) > 0 else "NÃO IDENTIFICADO",
        "7. Dívidas fiscais": "ALTO" if any(f.get("pontos",0) <= -20 and "pgfn" in f.get("fonte","").lower() for f in fontes) else "NÃO IDENTIFICADO",
        "8. PL negativo": "ALTO" if "patrimônio líquido negativo" in t or "passivo a descoberto" in t else "NÃO IDENTIFICADO",
        "9. Recuperação judicial": "CRÍTICO" if raw_jud.get("rj") or "recuperação judicial" in t else "NÃO IDENTIFICADO",
        "10. Crise reputacional": "ALTO" if any(f.get("pontos",0) <= -8 and "reputação" in f.get("fonte","").lower() for f in fontes) else "NÃO IDENTIFICADO",
    }


# =============================================================================
# RASTREABILIDADE — Registro de cada consulta
# =============================================================================
def registrar_rastreabilidade(cnpj: str, fontes: list, parecer: dict) -> dict:
    """Gera registro completo de rastreabilidade para auditoria."""
    return {
        "id_analise": f"PILDER-{cnpj}-{dt.datetime.now().strftime('%Y%m%d%H%M%S')}",
        "cnpj": cnpj,
        "data_hora": dt.datetime.now().isoformat(),
        "assinatura": ASSINATURA,
        "framework_evidencia": "CONFIRMACAO|EVIDENCIA|INDICIO|AUSENCIA",
        "fontes": [{
            "fonte": f.get("fonte",""),
            "status": f.get("status",""),
            "categoria_evidencia": f.get("categoria_evidencia",""),
            "confianca": CATEGORIAS_EVIDENCIA.get(
                f.get("categoria_evidencia",""), {}).get("confianca","Baixo"),
            "pontos": f.get("pontos",0),
            "consultado_em": f.get("consultado_em",""),
            "resumo": f.get("resumo",""),
        } for f in fontes],
        "rastreabilidade": parecer.get("rastreabilidade", {}),
        "blocos_confianca": parecer.get("blocos_confianca", {}),
        "via_ia": parecer.get("via_ia", False),
        "governo_pilder": {
            "P": "Problema identificado e estruturado",
            "I": f"Informação coletada de {len(fontes)} fontes",
            "L": "Leitura e classificação de evidências realizada",
            "D": "Decisão baseada em score, rating e flags",
            "E": "Execução: aprovação/negação conforme política",
            "R": "Revisão: monitoramento definido por nível de risco",
        }
    }


# =============================================================================
# CONSOLIDAÇÃO FINAL — integra tudo
# =============================================================================
def gerar_analise_completa(resultado: dict, balanco: dict,
                            cisp: dict, balanco_texto: str = "",
                            cisp_texto: str = "") -> dict:
    """
    Consolida análise completa com framework P.I.L.D.E.R™.
    """
    cnpj = resultado.get("cnpj", "")
    fontes = resultado.get("fontes", [])

    # Dados cadastrais da fonte Receita
    dados_cadastrais = {}
    for f in fontes:
        if "receita" in f.get("fonte","").lower():
            dados_cadastrais = {
                k: v for k, v in f.items()
                if k not in ("raw","evidence","status","resumo","detalhe",
                             "pontos","consultado_em","fonte")
            }
            break

    # Gera parecer sênior com framework completo
    parecer = gerar_parecer_analista_senior(
        cnpj, dados_cadastrais, fontes, balanco_texto, cisp_texto
    )

    # Rastreabilidade
    rastreio = registrar_rastreabilidade(cnpj, parecer["fontes_classificadas"], parecer)

    return {
        **resultado,
        "balanco_detalhado": balanco,
        "cisp_detalhado": cisp,
        "parecer_senior": parecer,
        "rastreabilidade": rastreio,
        "framework_evidencia": CATEGORIAS_EVIDENCIA,
        "assinatura": ASSINATURA,
        "relatorio_gerado_em": dt.datetime.now().isoformat(),
    }
