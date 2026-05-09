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

try:
    from novos_conectores import (
        consultar_cndt_tst,
        consultar_opensanctions,
        consultar_pep_opensanctions,
        consultar_pgfn_lista,
        consultar_cnd_receita,
        status_novos_conectores,
    )
    HAS_NOVOS_CONECTORES = True
except ImportError:
    HAS_NOVOS_CONECTORES = False

try:
    from analise_financeira_v3 import (
        analisar_balanco_completo as _bal_v3,
        analisar_cisp_completo as _cisp_v3,
    )
    HAS_FINANCEIRA_V3 = True
except ImportError:
    HAS_FINANCEIRA_V3 = False

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


# =========================
# Análise Financeira — usa módulo analise_financeira_v3 se disponível
# =========================
def analisar_balanco_completo(texto: str, nome_arquivo: str = "") -> dict:
    """Análise completa de balanço — usa v3 se disponível."""
    if HAS_FINANCEIRA_V3:
        return _bal_v3(texto, nome_arquivo)
    if not texto or len(texto.strip()) < 100:
        return {
            "disponivel": False, "arquivo": nome_arquivo,
            "status": "nao_consultado",
            "resumo": "Arquivo sem texto extraível ou não anexado",
            "pontos": -8, "red_flags": [], "yellow_flags": [],
            "green_flags": [], "indicadores": {},
            "parecer_gestor": f"{ASSINATURA}\nSem demonstrações financeiras disponíveis.",
        }
    t = texto.lower()
    red, yellow, green = [], [], []
    pts = 0
    ind = {}
    if any(p in t for p in ["prejuízo", "resultado negativo", "lucro negativo"]):
        red.append("🔴 Resultado negativo identificado"); pts -= 12
    if any(p in t for p in ["lucro líquido", "lucro do exercício"]):
        green.append("🟢 Resultado positivo (lucro) identificado"); pts += 8
    if "recuperação judicial" in t:
        red.append("🔴🚨 RECUPERAÇÃO JUDICIAL mencionada"); pts -= 45
    if "patrimônio líquido negativo" in t or "passivo a descoberto" in t:
        red.append("🔴 Patrimônio líquido negativo"); pts -= 20
    if "ressalva" in t:
        red.append("🔴 Ressalva de auditoria identificada"); pts -= 8
    if any(p in t for p in ["sem auditoria", "internos", "não auditado"]):
        red.append("🔴 Demonstrativos sem auditoria externa"); pts -= 5
    status = "confirmacao" if not red and green else "indicio" if len(red) <= 1 else "erro"
    return {
        "disponivel": True, "arquivo": nome_arquivo, "status": status,
        "resumo": f"{len(red)} red | {len(yellow)} yellow | {len(green)} green",
        "pontos": int(max(-50, min(25, pts))),
        "red_flags": red, "yellow_flags": yellow, "green_flags": green,
        "indicadores": ind,
        "parecer_gestor": f"{ASSINATURA}\nAnálise heurística básica. Instale analise_financeira_v3.py para análise completa.",
    }


def analisar_cisp_completo(texto: str, nome_arquivo: str = "") -> dict:
    """Análise completa de ficha CISP — usa v3 se disponível."""
    if HAS_FINANCEIRA_V3:
        return _cisp_v3(texto, nome_arquivo)
    if not texto or len(texto.strip()) < 50:
        return {
            "disponivel": False, "arquivo": nome_arquivo,
            "status": "nao_consultado",
            "resumo": "Ficha CISP não disponível",
            "pontos": 0, "red_flags": [], "yellow_flags": [],
            "green_flags": [], "indicadores": {},
            "parecer_gestor": "Sem ficha CISP para análise comportamental.",
        }
    t = texto.lower()
    red, yellow, green = [], [], []
    pts = 0
    ind = {}
    if any(p in t for p in ["inadimplente", "em atraso", "bloqueado"]):
        red.append("🔴 Histórico de inadimplência identificado"); pts -= 12
    if any(p in t for p in ["adimplente", "bom pagador", "pontual"]):
        green.append("🟢 Histórico positivo de pagamento"); pts += 8
    if "cheque sem fundos" in t or "ccf" in t:
        red.append("🔴 Cheque sem fundos registrado"); pts -= 15
    status = "confirmacao" if not red and green else "erro" if red else "indicio"
    return {
        "disponivel": True, "arquivo": nome_arquivo, "status": status,
        "resumo": f"{len(red)} red | {len(yellow)} yellow | {len(green)} green",
        "pontos": int(max(-30, min(15, pts))),
        "red_flags": red, "yellow_flags": yellow, "green_flags": green,
        "indicadores": ind,
        "parecer_gestor": f"{ASSINATURA}\nAnálise heurística básica. Instale analise_financeira_v3.py para análise completa.",
    }


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
    t = str(v).strip().replace("R$","").replace(".","").replace(",",".")
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
# Adaptadores de Fontes
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
                f"{'ATIVA' if ativa else situacao} | {anos:.1f} anos | {uf}/{municipio}" if anos else f"{'ATIVA' if ativa else situacao} | {uf}/{municipio}",
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
            should = [{"match": {"numeroProcesso": cnpj}}]
            if razao_social:
                should.append({"match_phrase": {"partes.nome": razao_social}})
            payload = {"query": {"bool": {"should": should}}, "size": 50}
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
    ]

    # Novos conectores gratuitos
    if HAS_NOVOS_CONECTORES:
        fontes.extend([
            consultar_pgfn_lista(cnpj),
            consultar_cndt_tst(cnpj, razao),
            consultar_opensanctions(razao, cnpj),
            consultar_pep_opensanctions(rec.get("qsa", []), cnpj),
            consultar_cnd_receita(cnpj),
        ])
    else:
        fontes.extend([
            fonte_resultado("PGFN / Dívida Ativa", "pendente",
                "Consulta PGFN requer integração. Ausência NÃO equivale a regularidade.", "", -5),
            fonte_resultado("TST / CNDT", "pendente",
                "Certidão trabalhista requer integração com TST.", "", -3),
            fonte_resultado("OpenSanctions / Sanções", "pendente",
                "Consulta de sanções internacionais pendente.", "", -2),
        ])

    fontes.extend([
        fonte_resultado("FGTS / CRF", "pendente",
            "CRF requer integração com Caixa. Exigir certidão antes da aprovação.", "", -3),
        fonte_resultado("Protestos / IEPTB", "pendente",
            "Consulta de protestos requer bureau especializado.", "", -4),
        fonte_resultado("Bureau de Crédito", "pendente",
            "Score bureau requer contrato. Alta relevância para análise B2B.", "", -6),
    ])

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
@app.post("/api/teste-upload")
async def teste_upload(
    cnpj: str = Form(...),
    balanco: Optional[UploadFile] = File(None),
    cisp: Optional[UploadFile] = File(None),
):
    bal_info = {"nome": balanco.filename, "tamanho": 0} if balanco else None
    cisp_info = {"nome": cisp.filename, "tamanho": 0} if cisp else None
    if balanco:
        conteudo = await balanco.read()
        bal_info["tamanho"] = len(conteudo)
        bal_info["texto_chars"] = len(extrair_texto_arquivo(conteudo, balanco.filename))
    if cisp:
        conteudo = await cisp.read()
        cisp_info["tamanho"] = len(conteudo)
        cisp_info["texto_chars"] = len(extrair_texto_arquivo(conteudo, cisp.filename))
    return {"cnpj": cnpj, "balanco": bal_info, "cisp": cisp_info}
@app.get("/api/conectores")
def status_conectores():
    base = {
        "receita_federal": {"status": "ativo", "tipo": "api_publica", "custo": "gratuito"},
        "simples_nacional": {"status": "ativo", "tipo": "api_publica", "custo": "gratuito"},
        "ceis_cnep": {"status": "ativo_parcial", "tipo": "api_publica", "custo": "gratuito"},
        "datajud_cnj": {"status": "ativo_parcial", "tipo": "api_publica", "custo": "gratuito"},
        "noticias_google": {"status": "ativo", "tipo": "rss_publico", "custo": "gratuito"},
        "balanco_pdf": {"status": "ativo", "tipo": "upload_extracao_real", "custo": "gratuito"},
        "cisp_credinfar": {"status": "ativo", "tipo": "upload_extracao_real", "custo": "gratuito"},
        "fgts_crf": {"status": "pendente", "tipo": "placeholder", "custo": "gratuito_manual"},
        "protestos_ieptb": {"status": "pendente", "tipo": "placeholder", "custo": "bureau"},
        "bureau_credito": {"status": "pendente", "tipo": "placeholder", "custo": "contrato"},
    }
    if HAS_NOVOS_CONECTORES:
        base.update(status_novos_conectores())
    return base
