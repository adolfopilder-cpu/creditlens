#!/usr/bin/env python3
"""
P.I.L.D.E.R™ – Backend FastAPI v4.0
Extração real de PDF + Análise de Gestor Financeiro Sênior
"""
from __future__ import annotations
import datetime as dt, json, os, re, io, base64, traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import pandas as pd

# Extração de PDF
try:
    import pdfplumber
    HAS_PDFPLUMBER = True
except ImportError:
    HAS_PDFPLUMBER = False

try:
    from pypdf import PdfReader
    HAS_PYPDF = True
except ImportError:
    HAS_PYPDF = False

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
TIMEOUT = 20
HEADERS = {"User-Agent": "PILDER-PRO/4.0"}
ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

try:
    from analise_detalhada_v2 import gerar_analise_completa, CATEGORIAS_EVIDENCIA
    HAS_ANALISE_DETALHADA = True
except ImportError:
    HAS_ANALISE_DETALHADA = False

app = FastAPI(title="P.I.L.D.E.R PRO API", version="4.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True,
                   allow_methods=["*"], allow_headers=["*"])

# =========================
# Extração de PDF — REAL
# =========================
def extrair_texto_pdf(conteudo_bytes: bytes) -> str:
    """
    Extrai texto de PDF usando pdfplumber (melhor para tabelas/layout)
    com fallback para pypdf.
    """
    texto = ""

    # Tentativa 1: pdfplumber (melhor para balanços com tabelas)
    if HAS_PDFPLUMBER:
        try:
            with pdfplumber.open(io.BytesIO(conteudo_bytes)) as pdf:
                partes = []
                for i, page in enumerate(pdf.pages):
                    # Extrai texto normal
                    t = page.extract_text() or ""
                    # Extrai tabelas e converte para texto
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            linha = " | ".join([str(c).strip() if c else "" for c in row])
                            if linha.strip():
                                t += "\n" + linha
                    partes.append(f"[PÁGINA {i+1}]\n{t}")
                texto = "\n\n".join(partes)
        except Exception as e:
            texto = ""

    # Tentativa 2: pypdf como fallback
    if not texto.strip() and HAS_PYPDF:
        try:
            reader = PdfReader(io.BytesIO(conteudo_bytes))
            partes = []
            for i, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                partes.append(f"[PÁGINA {i+1}]\n{t}")
            texto = "\n\n".join(partes)
        except Exception as e:
            texto = ""

    return texto.strip()


def extrair_texto_arquivo(conteudo_bytes: bytes, nome_arquivo: str = "") -> str:
    """Extrai texto de qualquer tipo de arquivo."""
    nome_lower = (nome_arquivo or "").lower()

    # PDF
    if nome_lower.endswith(".pdf") or conteudo_bytes[:4] == b"%PDF":
        return extrair_texto_pdf(conteudo_bytes)

    # Excel
    if nome_lower.endswith((".xlsx", ".xls")):
        try:
            df = pd.read_excel(io.BytesIO(conteudo_bytes), sheet_name=None)
            partes = []
            for sheet_name, sheet_df in df.items():
                partes.append(f"[ABA: {sheet_name}]\n{sheet_df.to_string()}")
            return "\n\n".join(partes)
        except Exception:
            pass

    # CSV
    if nome_lower.endswith(".csv"):
        try:
            df = pd.read_csv(io.BytesIO(conteudo_bytes), encoding="utf-8", errors="ignore")
            return df.to_string()
        except Exception:
            pass

    # Texto puro
    try:
        return conteudo_bytes.decode("utf-8", errors="ignore")
    except Exception:
        return ""


# =========================
# Utilitários
# =========================
def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")

def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    def calc(base, pesos):
        s = sum(int(d)*p for d,p in zip(base, pesos))
        r = s % 11
        return "0" if r < 2 else str(11-r)
    b = cnpj[:12]
    d1 = calc(b, [5,4,3,2,9,8,7,6,5,4,3,2])
    d2 = calc(b+d1, [6,5,4,3,2,9,8,7,6,5,4,3,2])
    return cnpj[-2:] == d1+d2

def apenas_numero(v):
    if v is None: return 0.0
    if isinstance(v, (int, float)): return float(v)
    t = str(v).strip().replace("R$","").replace(".", "").replace(",", ".")
    try: return float(t)
    except: return 0.0

def clamp(v, mn, mx): return max(mn, min(mx, v))

def years_since(s):
    if not s: return None
    for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
        try:
            return round((dt.date.today() - dt.datetime.strptime(s, fmt).date()).days/365.25, 2)
        except: continue
    return None

def fonte_resultado(nome, status, resumo, detalhe="", pontos=0.0, raw=None):
    return {
        "fonte": nome, "status": status, "resumo": resumo,
        "detalhe": detalhe, "pontos": pontos, "raw": raw or {},
        "consultado_em": dt.datetime.now().strftime("%d/%m/%Y %H:%M"),
    }

# =========================
# Análise REAL de Balanço — Gestor Financeiro Sênior
# =========================
def extrair_valor_monetario(texto: str, padrao: str) -> Optional[float]:
    """Extrai valor monetário próximo a um padrão."""
    patterns = [
        rf"{padrao}[^\d\n]{{0,50}}R?\$?\s*([\d\.,]+)",
        rf"([\d\.,]+)\s*[^\d\n]{{0,20}}{padrao}",
    ]
    for p in patterns:
        matches = re.findall(p, texto, re.IGNORECASE)
        if matches:
            for m in matches:
                try:
                    v = str(m).replace(".", "").replace(",", ".")
                    val = float(v)
                    if val > 0: return val
                except: continue
    return None

def analisar_balanco_completo(texto: str, nome_arquivo: str = "") -> dict:
    """
    Análise REAL do conteúdo extraído do balanço.
    Atua como Gestor Financeiro Sênior.
    """
    if not texto or len(texto.strip()) < 100:
        return {
            "disponivel": False,
            "texto_extraido": "",
            "paginas": 0,
            "status": "nao_consultado",
            "resumo": "Arquivo anexado mas sem texto extraível. Pode ser PDF escaneado sem OCR.",
            "pontos": -8,
            "red_flags": [],
            "yellow_flags": [],
            "green_flags": [],
            "indicadores": {},
            "parecer_gestor": (
                f"{ASSINATURA}\n\n"
                "PARECER DE BALANÇO — GESTOR FINANCEIRO SÊNIOR\n\n"
                "Documento recebido mas sem conteúdo textual extraível. "
                "Possíveis causas: PDF escaneado sem OCR, arquivo protegido ou imagem. "
                "Recomendo solicitação de novo arquivo em formato editável (Excel, CSV ou PDF com texto selecionável). "
                "Avaliação financeira aplicada de forma conservadora."
            ),
        }

    t = texto.lower()
    paginas = texto.count("[página")
    red_flags = []
    yellow_flags = []
    green_flags = []
    indicadores = {}
    pts = 0

    # ── RESULTADO / LUCRO / PREJUÍZO ──────────────────────────────────────
    if any(p in t for p in ["prejuízo do exercício", "prejuízo líquido", "resultado negativo",
                              "lucro negativo", "deficit", "perda líquida"]):
        red_flags.append("🔴 Resultado líquido NEGATIVO identificado — empresa operando com prejuízo")
        pts -= 12

    elif any(p in t for p in ["lucro do exercício", "lucro líquido", "resultado positivo",
                                "lucro antes", "resultado do exercício"]):
        # Tenta extrair o valor
        val = extrair_valor_monetario(texto, r"lucro l[íi]quido|lucro do exerc[íi]cio")
        if val:
            green_flags.append(f"🟢 Lucro líquido identificado: R$ {val:,.2f}")
        else:
            green_flags.append("🟢 Resultado positivo (lucro) identificado no exercício")
        pts += 8

    # ── RECEITA ───────────────────────────────────────────────────────────
    receita_val = extrair_valor_monetario(texto, r"receita l[íi]quida|receita bruta|faturamento")
    if receita_val:
        indicadores["receita_liquida"] = receita_val
        green_flags.append(f"🟢 Receita líquida identificada: R$ {receita_val:,.2f}")
        pts += 3

    if any(p in t for p in ["queda de receita", "redução de receita", "receita caiu",
                              "retração", "redução no faturamento"]):
        red_flags.append("🔴 Queda/redução de receita mencionada — risco de continuidade")
        pts -= 8

    if any(p in t for p in ["crescimento de receita", "aumento de receita", "expansão",
                              "crescimento do faturamento"]):
        green_flags.append("🟢 Crescimento de receita registrado")
        pts += 5

    # ── PATRIMÔNIO LÍQUIDO ────────────────────────────────────────────────
    pl_val = extrair_valor_monetario(texto, r"patrim[oô]nio l[íi]quido|pl ")
    if pl_val:
        indicadores["patrimonio_liquido"] = pl_val
        green_flags.append(f"🟢 Patrimônio líquido identificado: R$ {pl_val:,.2f}")
        pts += 4

    if any(p in t for p in ["patrimônio líquido negativo", "pl negativo",
                              "passivo a descoberto", "capital negativo"]):
        red_flags.append("🔴 PATRIMÔNIO LÍQUIDO NEGATIVO — passivo a descoberto / insolvência técnica")
        pts -= 20

    # ── ENDIVIDAMENTO / PASSIVO ───────────────────────────────────────────
    passivo_val = extrair_valor_monetario(texto, r"passivo total|total do passivo|total passivo")
    if passivo_val:
        indicadores["passivo_total"] = passivo_val

    if any(p in t for p in ["dívidas de longo prazo", "financiamentos de longo prazo",
                              "empréstimos de longo prazo"]):
        val = extrair_valor_monetario(texto, r"d[íi]vidas|financiamentos|empr[eé]stimos")
        msg = f"R$ {val:,.2f}" if val else "valor não extraído"
        yellow_flags.append(f"🟡 Endividamento de longo prazo identificado ({msg}) — avaliar capacidade de pagamento")
        pts -= 4

    if any(p in t for p in ["endividamento elevado", "alta alavancagem", "sobre-endividamento"]):
        red_flags.append("🔴 Endividamento elevado / alta alavancagem mencionado")
        pts -= 10

    # ── LIQUIDEZ ──────────────────────────────────────────────────────────
    if any(p in t for p in ["liquidez corrente", "índice de liquidez"]):
        val = extrair_valor_monetario(texto, r"liquidez corrente|[íi]ndice de liquidez")
        if val:
            indicadores["liquidez_corrente"] = val
            if val >= 1.5:
                green_flags.append(f"🟢 Liquidez corrente saudável: {val:.2f}")
                pts += 8
            elif val >= 1.0:
                yellow_flags.append(f"🟡 Liquidez corrente aceitável mas próxima do limite: {val:.2f}")
                pts += 2
            else:
                red_flags.append(f"🔴 Liquidez corrente abaixo de 1,0 ({val:.2f}) — risco de inadimplência com fornecedores")
                pts -= 12

    # ── EBITDA / MARGEM ───────────────────────────────────────────────────
    if "ebitda" in t:
        val = extrair_valor_monetario(texto, r"ebitda")
        if val:
            indicadores["ebitda"] = val
            green_flags.append(f"🟢 EBITDA identificado: R$ {val:,.2f}")
            pts += 5
        else:
            yellow_flags.append("🟡 EBITDA mencionado mas valor não extraído — solicitar demonstração detalhada")

    if any(p in t for p in ["margem negativa", "margem líquida negativa"]):
        red_flags.append("🔴 Margem líquida negativa identificada — resultado operacional comprometido")
        pts -= 10

    if any(p in t for p in ["margem positiva", "boa margem", "margem cresceu"]):
        green_flags.append("🟢 Margem positiva/crescente identificada")
        pts += 4

    # ── FLUXO DE CAIXA ────────────────────────────────────────────────────
    if any(p in t for p in ["fluxo de caixa negativo", "saída de caixa", "queima de caixa",
                              "cash burn", "caixa negativo"]):
        red_flags.append("🔴 Fluxo de caixa negativo — consumo de recursos operacionais")
        pts -= 14

    if any(p in t for p in ["geração de caixa", "fluxo positivo", "caixa gerado",
                              "fluxo de caixa positivo"]):
        green_flags.append("🟢 Geração de caixa positiva identificada")
        pts += 6

    # ── AUDITORIA ─────────────────────────────────────────────────────────
    if any(p in t for p in ["ressalva", "opinião com ressalva", "exceto por"]):
        red_flags.append("🔴 RESSALVA DE AUDITORIA identificada — verificar natureza e materialidade")
        pts -= 8

    if any(p in t for p in ["sem ressalva", "opinião não modificada", "auditoria independente",
                              "opinião limpa"]):
        green_flags.append("🟢 Balanço auditado sem ressalvas")
        pts += 5

    # ── SINAIS DE RJ / STRESS CRÍTICOS ───────────────────────────────────
    if "recuperação judicial" in t:
        red_flags.append("🔴🚨 RECUPERAÇÃO JUDICIAL mencionada no documento — RISCO CRÍTICO")
        pts -= 45

    if any(p in t for p in ["concordata", "falência", "insolvência", "liquidação"]):
        red_flags.append("🔴🚨 Termo crítico identificado: concordata/falência/insolvência/liquidação")
        pts -= 30

    if "parcelamento de dívida" in t or "renegociação" in t:
        yellow_flags.append("🟡 Parcelamento ou renegociação de dívidas mencionado — sinal de stress financeiro anterior")
        pts -= 5

    # ── CAPITAL SOCIAL ────────────────────────────────────────────────────
    capital = extrair_valor_monetario(texto, r"capital social")
    if capital:
        indicadores["capital_social"] = capital
        green_flags.append(f"🟢 Capital social identificado: R$ {capital:,.2f}")
        pts += 2

    # ── RESERVAS / DIVIDENDOS ─────────────────────────────────────────────
    if any(p in t for p in ["reserva de lucros", "reserva legal", "retenção de lucros"]):
        green_flags.append("🟢 Reservas de lucros identificadas — empresa retém resultados")
        pts += 3

    if "distribuição de dividendos" in t or "juros sobre capital próprio" in t:
        green_flags.append("🟢 Distribuição de dividendos/JCP — empresa remunera acionistas")
        pts += 2

    # ── IMOBILIZADO / ATIVO ───────────────────────────────────────────────
    ativo_total = extrair_valor_monetario(texto, r"ativo total|total do ativo|total ativo")
    if ativo_total:
        indicadores["ativo_total"] = ativo_total
        green_flags.append(f"🟢 Ativo total identificado: R$ {ativo_total:,.2f}")

    # ── GERA PARECER DO GESTOR ────────────────────────────────────────────
    parecer = _gerar_parecer_gestor(red_flags, yellow_flags, green_flags, indicadores, pts, paginas, nome_arquivo)

    status = "confirmacao" if not red_flags and green_flags else \
             "indicio" if len(red_flags) <= 1 else "erro"

    resumo_partes = []
    if red_flags:
        resumo_partes.append(f"⚠ {len(red_flags)} RED FLAG(S)")
    if yellow_flags:
        resumo_partes.append(f"{len(yellow_flags)} atenção")
    if green_flags:
        resumo_partes.append(f"{len(green_flags)} positivo(s)")
    resumo = " | ".join(resumo_partes) if resumo_partes else "Balanço analisado sem sinais críticos"

    return {
        "disponivel": True,
        "arquivo": nome_arquivo,
        "paginas": paginas or 1,
        "texto_extraido": texto[:2000] + "..." if len(texto) > 2000 else texto,
        "status": status,
        "resumo": resumo,
        "pontos": int(round(clamp(pts, -50, 25))),
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "green_flags": green_flags,
        "indicadores": indicadores,
        "parecer_gestor": parecer,
    }


def _gerar_parecer_gestor(red_flags, yellow_flags, green_flags, indicadores, pts, paginas, arquivo):
    """Gera parecer como Gestor Financeiro Sênior."""
    linhas = [
        f"{ASSINATURA}",
        f"PARECER DE ANÁLISE DE BALANÇO — GESTOR FINANCEIRO SÊNIOR",
        f"Arquivo: {arquivo} | Páginas lidas: {paginas} | Pontuação financeira: {'+' if pts > 0 else ''}{pts}",
        "=" * 60,
    ]

    if red_flags:
        linhas.append("\n🔴 RED FLAGS — ALERTAS CRÍTICOS:")
        for f in red_flags:
            linhas.append(f"  {f}")
        linhas.append("")

    if yellow_flags:
        linhas.append("🟡 YELLOW FLAGS — PONTOS DE ATENÇÃO:")
        for f in yellow_flags:
            linhas.append(f"  {f}")
        linhas.append("")

    if green_flags:
        linhas.append("🟢 GREEN FLAGS — ASPECTOS POSITIVOS:")
        for f in green_flags:
            linhas.append(f"  {f}")
        linhas.append("")

    if indicadores:
        linhas.append("📊 INDICADORES EXTRAÍDOS DO DOCUMENTO:")
        for k, v in indicadores.items():
            label = k.replace("_", " ").title()
            if isinstance(v, float) and v > 100:
                linhas.append(f"  {label}: R$ {v:,.2f}")
            elif isinstance(v, float):
                linhas.append(f"  {label}: {v:.2f}")
            else:
                linhas.append(f"  {label}: {v}")
        linhas.append("")

    # Conclusão
    linhas.append("📋 CONCLUSÃO DO GESTOR:")
    if any("recuperação judicial" in f.lower() or "falência" in f.lower() for f in red_flags):
        linhas.append("  SITUAÇÃO CRÍTICA. Empresa com sinal explícito de recuperação judicial ou insolvência.")
        linhas.append("  RECOMENDAÇÃO: NEGAR crédito. Acionar jurídico e revisar toda a carteira com este cliente.")
    elif len(red_flags) >= 3:
        linhas.append("  Perfil financeiro DETERIORADO. Múltiplos sinais de stress identificados.")
        linhas.append("  RECOMENDAÇÃO: Restringir limite ao mínimo. Exigir garantias reais e aval pessoal dos sócios.")
    elif len(red_flags) >= 1:
        linhas.append("  Perfil financeiro sob PRESSÃO. Sinais de alerta presentes.")
        linhas.append("  RECOMENDAÇÃO: Aprovar com cautela. Limite reduzido, prazo curto, monitoramento mensal.")
    elif len(yellow_flags) >= 2:
        linhas.append("  Perfil financeiro MODERADO. Pontos de atenção que merecem acompanhamento.")
        linhas.append("  RECOMENDAÇÃO: Aprovar com monitoramento trimestral e revisão de limite.")
    elif green_flags:
        linhas.append("  Perfil financeiro SAUDÁVEL. Indicadores positivos predominam.")
        linhas.append("  RECOMENDAÇÃO: Aprovar conforme política interna. Monitoramento semestral.")
    else:
        linhas.append("  Análise inconclusiva — poucos dados estruturados extraídos do documento.")
        linhas.append("  RECOMENDAÇÃO: Solicitar balanço auditado em formato estruturado para análise completa.")

    return "\n".join(linhas)


# =========================
# Análise REAL de Ficha CISP
# =========================
def analisar_cisp_completo(texto: str, nome_arquivo: str = "") -> dict:
    """Análise real da ficha CISP como Gestor Financeiro."""
    if not texto or len(texto.strip()) < 50:
        return {
            "disponivel": False,
            "arquivo": nome_arquivo,
            "status": "nao_consultado",
            "resumo": "Ficha CISP não anexada ou sem conteúdo.",
            "pontos": 0,
            "red_flags": [],
            "yellow_flags": [],
            "green_flags": [],
            "parecer_gestor": "Sem ficha CISP para análise de comportamento interno.",
        }

    t = texto.lower()
    red_flags = []
    yellow_flags = []
    green_flags = []
    pts = 0

    # Inadimplência
    if any(p in t for p in ["inadimplente", "em atraso", "vencido há", "atraso recorrente",
                              "bloqueado", "negativado", "protesto"]):
        red_flags.append("🔴 Histórico de inadimplência/atraso identificado na ficha")
        pts -= 12

    # Status positivo
    if any(p in t for p in ["adimplente", "bom pagador", "pontual", "em dia", "sem restrição"]):
        green_flags.append("🟢 Histórico positivo de pagamento — cliente pontual")
        pts += 8

    # Aging
    for periodo in ["90", "60", "120"]:
        if f"acima de {periodo}" in t or f"> {periodo}" in t or f"+{periodo}" in t:
            red_flags.append(f"🔴 Aging acima de {periodo} dias identificado — nível crítico de inadimplência")
            pts -= 8

    # Limite e aprovações
    val_limite = extrair_valor_monetario(texto, r"limite|limite de cr[eé]dito|limite aprovado")
    if val_limite:
        green_flags.append(f"🟢 Limite de crédito registrado: R$ {val_limite:,.2f}")
        pts += 3

    # Score/rating interno
    if any(p in t for p in ["score", "rating", "classificação"]):
        yellow_flags.append("🟡 Score/rating interno mencionado — verificar nota e histórico de evolução")

    # Concentração
    if any(p in t for p in ["concentração alta", "concentração elevada", "cliente concentrado"]):
        yellow_flags.append("🟡 Alta concentração de risco — cliente representa parcela relevante da carteira")
        pts -= 5

    # Garantias
    if any(p in t for p in ["garantia", "aval", "fiador", "hipoteca", "penhor"]):
        green_flags.append("🟢 Garantia ou aval formalizado registrado na ficha")
        pts += 5

    # Relacionamento
    if any(p in t for p in ["cliente há", "anos de relacionamento", "relacionamento de longo"]):
        green_flags.append("🟢 Relacionamento comercial de longo prazo com a empresa")
        pts += 4

    # Volume em aberto
    vol = extrair_valor_monetario(texto, r"volume em aberto|saldo devedor|d[eé]bito atual|em aberto")
    if vol:
        yellow_flags.append(f"🟡 Volume em aberto identificado: R$ {vol:,.2f}")
        pts -= 3

    # Gera parecer
    linhas = [
        f"{ASSINATURA}",
        "PARECER DE FICHA CISP / COMPORTAMENTO INTERNO",
        f"Arquivo: {nome_arquivo}",
        "=" * 60,
    ]
    if red_flags:
        linhas.append("\n🔴 RED FLAGS:")
        for f in red_flags: linhas.append(f"  {f}")
    if yellow_flags:
        linhas.append("\n🟡 YELLOW FLAGS:")
        for f in yellow_flags: linhas.append(f"  {f}")
    if green_flags:
        linhas.append("\n🟢 GREEN FLAGS:")
        for f in green_flags: linhas.append(f"  {f}")

    linhas.append("\n📋 PARECER DO GESTOR:")
    if red_flags:
        linhas.append("  Comportamento interno PREOCUPANTE. Histórico negativo identificado.")
        linhas.append("  RECOMENDAÇÃO: Revisão imediata do limite. Cobrança ativa. Considerar redução ou bloqueio.")
    elif yellow_flags and not green_flags:
        linhas.append("  Comportamento interno MODERADO. Pontos de atenção presentes.")
        linhas.append("  RECOMENDAÇÃO: Monitoramento mensal. Manter limite atual com cautela.")
    elif green_flags:
        linhas.append("  Comportamento interno POSITIVO. Cliente com histórico favorável.")
        linhas.append("  RECOMENDAÇÃO: Manter ou ampliar limite conforme política. Revisão semestral.")

    return {
        "disponivel": True,
        "arquivo": nome_arquivo,
        "status": "confirmacao" if not red_flags else "erro",
        "resumo": f"{len(red_flags)} red | {len(yellow_flags)} yellow | {len(green_flags)} green",
        "pontos": int(round(clamp(pts, -20, 15))),
        "red_flags": red_flags,
        "yellow_flags": yellow_flags,
        "green_flags": green_flags,
        "parecer_gestor": "\n".join(linhas),
    }


# =========================
# Adaptadores de fontes (mantidos da v3)
# =========================
def consultar_receita(cnpj):
    for url in [f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
                f"https://receitaws.com.br/v1/cnpj/{cnpj}"]:
        try:
            r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code != 200: continue
            j = r.json()
            razao = j.get("razao_social","") or j.get("nome","")
            situacao = j.get("descricao_situacao_cadastral","") or j.get("situacao","")
            abertura = j.get("data_inicio_atividade","") or j.get("abertura","")
            cnae = j.get("cnae_fiscal_descricao","") or ""
            capital = apenas_numero(j.get("capital_social"))
            uf = j.get("uf","")
            municipio = j.get("municipio","")
            qsa = j.get("qsa",[]) or []
            anos = years_since(abertura)
            ativa = "ativa" in situacao.lower() if situacao else False
            pts = 8 if ativa else -15
            if anos: pts += 8 if anos>=10 else 4 if anos>=3 else -4
            if capital > 0: pts += 2
            if qsa: pts += 2
            return {**fonte_resultado("Receita Federal / Cadastro CNPJ",
                "confirmacao" if ativa else "indicio",
                f"{'ATIVA' if ativa else situacao} | {anos:.1f} anos | {uf}/{municipio}",
                f"Razão: {razao} | CNAE: {cnae} | Capital: R$ {capital:,.2f} | Sócios: {len(qsa)}",
                pts, j),
                "razao_social": razao, "situacao": situacao, "abertura": abertura,
                "cnae": cnae, "capital": capital, "uf": uf, "municipio": municipio,
                "qsa": qsa, "anos_mercado": anos}
        except: continue
    return fonte_resultado("Receita Federal / Cadastro CNPJ", "erro", "Falha em todas as fontes", pontos=-8)

def consultar_simples(cnpj):
    try:
        r = requests.get(f"https://brasilapi.com.br/api/simples/v1/{cnpj}", headers=HEADERS, timeout=TIMEOUT)
        if r.status_code == 200:
            j = r.json()
            simples = j.get("simples_nacional", False) or j.get("optante_simples_nacional", False)
            mei = j.get("mei", False)
            return fonte_resultado("Simples Nacional / MEI", "confirmacao",
                f"{'Optante Simples' if simples else 'Não optante'} | MEI: {'Sim' if mei else 'Não'}",
                "", 2 if simples else 0, j)
    except: pass
    return fonte_resultado("Simples Nacional / MEI", "nao_consultado", "Indisponível")

def consultar_ceis(cnpj):
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/ceis?cnpjSancionado={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CEIS – Empresas Inidôneas e Suspensas", "confirmacao",
                    f"⚠ LISTADA NO CEIS: {len(dados)} sanção(ões)", str(dados[0])[:200], -25)
            return fonte_resultado("CEIS", "ausencia", "Sem registros no CEIS", "", 3)
    except: pass
    return fonte_resultado("CEIS", "nao_consultado", "Consulta CEIS não disponível", "", -2)

def consultar_cnep(cnpj):
    try:
        url = f"https://api.portaldatransparencia.gov.br/api-de-dados/cnep?cnpjSancionado={cnpj}&pagina=1"
        r = requests.get(url, headers={**HEADERS,"chave-api-dados":"demo"}, timeout=TIMEOUT)
        if r.status_code == 200:
            dados = r.json()
            if isinstance(dados, list) and len(dados) > 0:
                return fonte_resultado("CNEP – Empresas Punidas", "confirmacao",
                    f"⚠ LISTADA NO CNEP: {len(dados)} punição(ões)", str(dados[0])[:200], -20)
            return fonte_resultado("CNEP", "ausencia", "Sem registros", "", 3)
    except: pass
    return fonte_resultado("CNEP", "nao_consultado", "Indisponível", "", -2)

def consultar_datajud(cnpj, razao_social=""):
    api_key = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"
    tribunais = [("TJSP","api_publica_tjsp"),("TJRJ","api_publica_tjrj"),
                 ("TJMG","api_publica_tjmg"),("TRF1","api_publica_trf1"),
                 ("TRT2","api_publica_trt2")]
    total = execucoes = trabalhistas = 0
    rj = False
    detalhes = []
    for nome, idx in tribunais:
        try:
            url = f"https://api-publica.datajud.cnj.jus.br/{idx}/_search"
            payload = {"query":{"bool":{"should":[
                {"match":{"numeroProcesso":cnpj}},
                {"match_phrase":{"partes.nome":razao_social}} if razao_social else {}
            ]}},"size":50}
            r = requests.post(url, json=payload, headers={**HEADERS,"Authorization":api_key}, timeout=15)
            if r.status_code == 200:
                hits = r.json().get("hits",{})
                t = hits.get("total",{}).get("value",0)
                total += t
                itens = hits.get("hits",[])
                e = sum(1 for h in itens if "execu" in str(h.get("_source",{}).get("classeProcessual","")).lower())
                tb = sum(1 for h in itens if "trabalh" in str(h.get("_source",{}).get("classeProcessual","")).lower())
                execucoes += e; trabalhistas += tb
                if any("recupera" in str(h.get("_source",{})).lower() for h in itens): rj = True
                if t > 0: detalhes.append(f"{nome}: {t} proc | exec:{e} trab:{tb}")
        except: pass
    pts = 0
    if rj: pts -= 45
    if execucoes >= 10: pts -= 12
    elif execucoes > 0: pts -= 5
    if total >= 100: pts -= 10
    elif total >= 20: pts -= 5
    elif total > 0: pts += 2
    else: pts += 3
    resumo = f"{total} processo(s) | Execuções: {execucoes} | Trabalhistas: {trabalhistas}"
    if rj: resumo = "⚠ RECUPERAÇÃO JUDICIAL | " + resumo
    return fonte_resultado("DataJud / CNJ – Processos Judiciais",
        "confirmacao" if total > 0 else "ausencia", resumo,
        " | ".join(detalhes) or "Sem processos", pts,
        {"total":total,"execucoes":execucoes,"trabalhistas":trabalhistas,"rj":rj})

def consultar_noticias(razao_social):
    try:
        termo = razao_social.replace(" ","+")
        url = f"https://news.google.com/rss/search?q={termo}+fraude+OR+escandalo+OR+falencia+OR+recuperacao&hl=pt-BR&gl=BR&ceid=BR:pt-419"
        r = requests.get(url, headers=HEADERS, timeout=10)
        if r.status_code == 200:
            count = r.text.count("<item>")
            if count > 5:
                return fonte_resultado("Reputação / Mídia", "indicio",
                    f"⚠ {count} notícias negativas encontradas", "", -8)
            elif count > 0:
                return fonte_resultado("Reputação / Mídia", "indicio",
                    f"{count} notícia(s) com termos negativos", "", -3)
            return fonte_resultado("Reputação / Mídia", "ausencia", "Sem notícias negativas", "", 2)
    except: pass
    return fonte_resultado("Reputação / Mídia", "nao_consultado", "Indisponível", "", -2)

def classificar_setor(cnae):
    cnae_lower = (cnae or "").lower()
    HIGH = ["cobran","constru","transporte","moda","varejista","factoring"]
    LOW = ["energia","saneamento","farmac","alimentos","saude","educac"]
    risco = "medio_alto" if any(t in cnae_lower for t in HIGH) else \
            "baixo" if any(t in cnae_lower for t in LOW) else "medio"
    pts = {"baixo":8,"medio":2,"medio_alto":-6}.get(risco,0)
    return {**fonte_resultado("Classificação Setorial CNAE","indicio",
        f"Setor: {cnae[:60]} | Risco: {risco}","",pts),
        "risco_setorial":risco,"setor":cnae}

# =========================
# Motor de Score
# =========================
def calcular_score(fontes, bal, cisp):
    base = 50.0
    pts_fontes = sum(f.get("pontos",0) for f in fontes)
    pts_bal = bal.get("pontos", 0)
    pts_cisp = cisp.get("pontos", 0)
    score = int(round(clamp(base + pts_fontes + pts_bal + pts_cisp, 0, 100)))

    def rating(s):
        for t,r in [(90,"AAA"),(82,"AA"),(74,"A"),(66,"BBB"),(58,"BB"),(48,"B"),(36,"C")]:
            if s >= t: return r
        return "D"

    def risco(s): return "baixo" if s>=75 else "medio" if s>=50 else "alto"
    def pd(s): return round(clamp(60-(s*0.55),1,80),1)

    def rec(s):
        if s >= 75: return ("Limite padrão ou acima da média","28 a 35 dias",
                           ["cessão de recebíveis para volumes maiores"],"Monitoramento trimestral")
        if s >= 50: return ("Limite conservador escalonado por performance","14 a 28 dias",
                           ["aval","cessão de recebíveis"],"Monitoramento mensal")
        return ("Limite reduzido ou operação pontual","7 a 14 dias",
               ["pagamento antecipado parcial","garantia real","seguro de crédito"],
               "Monitoramento semanal com gatilhos de bloqueio")

    rat = rating(score)
    ris = risco(score)
    pd_val = pd(score)
    limite, prazo, garantias, monitor = rec(score)

    # Consolida flags de todas as fontes + balanço + CISP
    red_flags = [f["resumo"] for f in fontes if f.get("pontos",0) <= -10]
    red_flags += bal.get("red_flags", [])
    red_flags += cisp.get("red_flags", [])

    yellow_flags = [f["resumo"] for f in fontes if -10 < f.get("pontos",0) < 0]
    yellow_flags += bal.get("yellow_flags", [])
    yellow_flags += cisp.get("yellow_flags", [])

    green_flags = [f["resumo"] for f in fontes if f.get("pontos",0) > 0]
    green_flags += bal.get("green_flags", [])
    green_flags += cisp.get("green_flags", [])

    sinais_rj = [f["resumo"] for f in fontes if "recupera" in f.get("resumo","").lower()]

    return {
        "score": score, "rating": rat, "pd": pd_val,
        "classificacao_risco": ris, "limite_sugerido": limite,
        "prazo_sugerido": prazo, "garantias_recomendadas": garantias,
        "plano_monitoramento": monitor,
        "red_flags": list(dict.fromkeys(red_flags)),
        "yellow_flags": list(dict.fromkeys(yellow_flags)),
        "green_flags": list(dict.fromkeys(green_flags)),
        "sinais_rj": sinais_rj,
        "memoria_calculo": {
            "base": base, "pts_fontes": pts_fontes,
            "pts_balanco": pts_bal, "pts_cisp": pts_cisp,
            "score_final": score
        },
    }

# =========================
# Orquestração
# =========================
def analisar_cnpj_completo(cnpj, bytes_balanco=None, bytes_cisp=None,
                            nome_balanco="", nome_cisp=""):
    cnpj = limpar_cnpj(cnpj)
    if not validar_cnpj(cnpj):
        raise ValueError(f"CNPJ inválido: {cnpj}")

    # Extrai texto REAL dos PDFs/arquivos
    texto_balanco = ""
    texto_cisp = ""
    if bytes_balanco:
        texto_balanco = extrair_texto_arquivo(bytes_balanco, nome_balanco)
    if bytes_cisp:
        texto_cisp = extrair_texto_arquivo(bytes_cisp, nome_cisp)

    # Consulta fontes
    rec = consultar_receita(cnpj)
    razao = rec.get("razao_social","")
    cnae = rec.get("cnae","")

    fontes = [
        rec,
        consultar_simples(cnpj),
        consultar_ceis(cnpj),
        consultar_cnep(cnpj),
        consultar_datajud(cnpj, razao),
        consultar_noticias(razao),
        classificar_setor(cnae),
        fonte_resultado("PGFN / Dívida Ativa", "pendente",
            "Consulta PGFN requer integração. Ausência NÃO equivale a regularidade.", "", -5),
        fonte_resultado("FGTS / CRF", "pendente",
            "CRF requer integração com Caixa. Exigir certidão antes da aprovação.", "", -3),
        fonte_resultado("Protestos / IEPTB", "pendente",
            "Consulta de protestos requer bureau especializado.", "", -4),
        fonte_resultado("Bureau de Crédito", "pendente",
            "Score bureau requer contrato. Alta relevância para análise B2B.", "", -6),
    ]

    # Análise real dos documentos
    bal = analisar_balanco_completo(texto_balanco, nome_balanco)
    cisp = analisar_cisp_completo(texto_cisp, nome_cisp)

    # Score
    score_data = calcular_score(fontes, bal, cisp)

    return {
        "cnpj": cnpj,
        "empresa": razao,
        **score_data,
        "fontes": fontes,
        "fontes_consultadas": len([f for f in fontes if f["status"] not in ["pendente","nao_consultado"]]),
        "fontes_pendentes": len([f for f in fontes if f["status"] in ["pendente","nao_consultado"]]),
        "total_fontes": len(fontes),
        "balanco_detalhado": bal,
        "cisp_detalhado": cisp,
        "assinatura": ASSINATURA,
        "analisado_em": dt.datetime.now().isoformat(),
    }

# =========================
# Geração de PDF — corrigido
# =========================
def gerar_pdf(resultado: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1.4*cm, rightMargin=1.4*cm,
                            topMargin=1.2*cm, bottomMargin=1.2*cm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], leading=13, fontSize=8)
    small = ParagraphStyle("Small", parent=styles["BodyText"], leading=11, fontSize=7)
    elements = []

    # Cabeçalho
    elements.append(Paragraph(ASSINATURA, styles["Title"]))
    empresa = resultado.get("empresa","") or resultado.get("cnpj","")
    elements.append(Paragraph(f"Análise de Crédito — {empresa}", styles["Heading2"]))
    elements.append(Spacer(1, 6))

    # Resumo
    rows = [
        ["CNPJ", resultado.get("cnpj","")],
        ["Score", str(resultado.get("score",""))],
        ["Rating", resultado.get("rating","")],
        ["PD Estimada", f"{resultado.get('pd',0):.1f}%"],
        ["Risco", resultado.get("classificacao_risco","")],
        ["Limite sugerido", resultado.get("limite_sugerido","")],
        ["Prazo sugerido", resultado.get("prazo_sugerido","")],
        ["Analisado em", str(resultado.get("analisado_em",""))[:19]],
    ]
    t = Table(rows, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ("GRID",(0,0),(-1,-1),0.3,colors.grey),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("FONTSIZE",(0,0),(-1,-1),8),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
    ]))
    elements.append(t)
    elements.append(Spacer(1,8))

    # Red/Yellow/Green flags
    for titulo, items, cor in [
        ("RED FLAGS", resultado.get("red_flags",[]), colors.red),
        ("YELLOW FLAGS", resultado.get("yellow_flags",[]), colors.orange),
        ("GREEN FLAGS", resultado.get("green_flags",[]), colors.green),
    ]:
        if items:
            elements.append(Paragraph(titulo, styles["Heading3"]))
            for item in items[:10]:
                elements.append(Paragraph(f"• {item[:150]}", body))
            elements.append(Spacer(1,4))

    # Balanço
    bal = resultado.get("balanco_detalhado",{})
    if bal.get("disponivel"):
        elements.append(Paragraph("ANÁLISE DE BALANÇO", styles["Heading2"]))
        elements.append(Paragraph(bal.get("arquivo",""), small))
        parecer = bal.get("parecer_gestor","")
        for linha in parecer.split("\n")[:40]:
            if linha.strip():
                elements.append(Paragraph(linha[:180], small))
        elements.append(Spacer(1,6))

    # CISP
    cisp = resultado.get("cisp_detalhado",{})
    if cisp.get("disponivel"):
        elements.append(Paragraph("ANÁLISE DE FICHA CISP", styles["Heading2"]))
        parecer_cisp = cisp.get("parecer_gestor","")
        for linha in parecer_cisp.split("\n")[:20]:
            if linha.strip():
                elements.append(Paragraph(linha[:180], small))
        elements.append(Spacer(1,6))

    # Fontes
    elements.append(Paragraph("FONTES CONSULTADAS", styles["Heading2"]))
    for f in resultado.get("fontes",[]):
        elements.append(Paragraph(
            f"[{f['status'].upper()}] {f['fonte']}: {f['resumo'][:120]}", small))

    # Rodapé
    elements.append(Spacer(1,10))
    elements.append(Paragraph(ASSINATURA, styles["Heading3"]))

    doc.build(elements)
    return buffer.getvalue()

# =========================
# Rotas
# =========================
class CNPJRequest(BaseModel):
    cnpj: str

@app.get("/")
def root():
    return {"status": "ok", "app": ASSINATURA, "version": "4.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": dt.datetime.now().isoformat(),
            "pdfplumber": HAS_PDFPLUMBER, "pypdf": HAS_PYPDF}

@app.post("/api/analisar")
def analisar(req: CNPJRequest):
    try:
        resultado = analisar_cnpj_completo(req.cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/analisar/{cnpj}")
def analisar_get(cnpj: str):
    try:
        resultado = analisar_cnpj_completo(cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analisar-com-anexo")
async def analisar_com_anexo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    try:
        bytes_bal = bytes_cisp = None
        nome_bal = nome_cisp = ""
        if balanco:
            bytes_bal = await balanco.read()
            nome_bal = balanco.filename or ""
        if cisp:
            bytes_cisp = await cisp.read()
            nome_cisp = cisp.filename or ""
        resultado = analisar_cnpj_completo(cnpj, bytes_bal, bytes_cisp, nome_bal, nome_cisp)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pdf/{cnpj}")
def baixar_pdf(cnpj: str):
    try:
        resultado = analisar_cnpj_completo(cnpj)
        pdf_bytes = gerar_pdf(resultado)
        # Encoding correto para base64
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        return JSONResponse(content={
            "pdf_base64": pdf_b64,
            "filename": f"PILDER_analise_{limpar_cnpj(cnpj)}.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lote")
async def processar_lote(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        if "cnpj" not in df.columns:
            raise HTTPException(status_code=422, detail="Coluna 'cnpj' não encontrada.")
        cnpjs = [limpar_cnpj(str(v)) for v in df["cnpj"].dropna().tolist()]
        resultados, erros = [], []
        for cnpj in cnpjs[:200]:
            try:
                resultados.append(analisar_cnpj_completo(cnpj))
            except Exception as e:
                erros.append({"cnpj": cnpj, "erro": str(e)})
        return JSONResponse(content={
            "processados": len(resultados), "erros": len(erros),
            "resultados": resultados, "erros_detalhe": erros,
        })
    except HTTPException: raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/analisar-completo")
async def analisar_completo(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    """
    Análise completa P.I.L.D.E.R™:
    - Extração real de PDF
    - Framework CONFIRMAÇÃO|EVIDÊNCIA|INDÍCIO|AUSÊNCIA
    - Parecer Analista Sênior (IA ou regras)
    - Rastreabilidade completa
    - 10 sinais de RJ/stress
    - Nível de confiança por bloco
    """
    try:
        bytes_bal = bytes_cisp_data = None
        nome_bal = nome_cisp = ""
        texto_bal = texto_cisp = ""

        if balanco:
            bytes_bal = await balanco.read()
            nome_bal = balanco.filename or ""
            texto_bal = extrair_texto_arquivo(bytes_bal, nome_bal)

        if cisp:
            bytes_cisp_data = await cisp.read()
            nome_cisp = cisp.filename or ""
            texto_cisp = extrair_texto_arquivo(bytes_cisp_data, nome_cisp)

        resultado = analisar_cnpj_completo(
            cnpj, bytes_bal, bytes_cisp_data, nome_bal, nome_cisp
        )

        bal = analisar_balanco_completo(texto_bal, nome_bal)
        cisp_anal = analisar_cisp_completo(texto_cisp, nome_cisp)

        if HAS_ANALISE_DETALHADA:
            relatorio = gerar_analise_completa(
                resultado, bal, cisp_anal, texto_bal, texto_cisp
            )
        else:
            relatorio = {
                **resultado,
                "balanco_detalhado": bal,
                "cisp_detalhado": cisp_anal,
                "assinatura": ASSINATURA,
                "relatorio_gerado_em": dt.datetime.now().isoformat(),
            }

        return JSONResponse(content=relatorio)

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro: {e}")

@app.get("/api/conectores")
def status_conectores():
    return {
        "receita_federal": {"status": "ativo", "tipo": "api_publica"},
        "simples_nacional": {"status": "ativo", "tipo": "api_publica"},
        "ceis_cnep": {"status": "ativo_parcial", "tipo": "api_publica"},
        "datajud_cnj": {"status": "ativo_parcial", "tipo": "api_publica"},
        "noticias": {"status": "ativo", "tipo": "rss_publico"},
        "balanco_pdf": {"status": "ativo", "tipo": "upload_com_extracao_real"},
        "cisp_pdf": {"status": "ativo", "tipo": "upload_com_extracao_real"},
        "pgfn": {"status": "pendente", "tipo": "placeholder"},
        "fgts": {"status": "pendente", "tipo": "placeholder"},
        "bureau_credito": {"status": "pendente", "tipo": "placeholder"},
    }
