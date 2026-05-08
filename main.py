#!/usr/bin/env python3
"""
CreditLens — Backend FastAPI
Pipeline de análise de crédito por CNPJ
"""
from __future__ import annotations

import datetime as dt
import json
import math
import os
import re
import traceback
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
import io
import tempfile

# =========================
# Config
# =========================
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
TIMEOUT = 20
HEADERS = {"User-Agent": "CreditLens/2.0"}

app = FastAPI(title="CreditLens API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Utilitários
# =========================
def limpar_cnpj(cnpj: str) -> str:
    return re.sub(r"\D", "", cnpj or "")

def validar_cnpj(cnpj: str) -> bool:
    cnpj = limpar_cnpj(cnpj)
    if len(cnpj) != 14 or cnpj == cnpj[0] * 14:
        return False
    def calc_digito(base: str, pesos: List[int]) -> str:
        soma = sum(int(d) * p for d, p in zip(base, pesos))
        resto = soma % 11
        return "0" if resto < 2 else str(11 - resto)
    base_12 = cnpj[:12]
    dig1 = calc_digito(base_12, [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    dig2 = calc_digito(base_12 + dig1, [6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2])
    return cnpj[-2:] == dig1 + dig2

def apenas_numero(valor: Any) -> float:
    if valor is None:
        return 0.0
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace("R$", "").replace(".", "").replace(",", ".")
    try:
        return float(texto)
    except ValueError:
        return 0.0

def clamp(valor: float, minimo: float, maximo: float) -> float:
    return max(minimo, min(maximo, valor))

def years_since(date_str: Optional[str]) -> Optional[float]:
    if not date_str:
        return None
    for fmt in ["%Y-%m-%d", "%d/%m/%Y"]:
        try:
            d = dt.datetime.strptime(date_str, fmt).date()
            return round((dt.date.today() - d).days / 365.25, 2)
        except ValueError:
            continue
    return None

# =========================
# Modelos de dados
# =========================
@dataclass
class Evidence:
    source: str
    status: str
    summary: str
    raw: Dict[str, Any] = field(default_factory=dict)

@dataclass
class ReceitaData:
    cnpj: str = ""
    razao_social: str = ""
    nome_fantasia: str = ""
    situacao_cadastral: str = ""
    data_abertura: str = ""
    natureza_juridica: str = ""
    cnae_principal: str = ""
    cnae_secundarios: List[str] = field(default_factory=list)
    capital_social: float = 0.0
    porte: str = ""
    uf: str = ""
    municipio: str = ""
    qsa: List[Dict[str, Any]] = field(default_factory=list)
    evidence: Evidence = field(default_factory=lambda: Evidence("receita", "nao_consultado", "Não consultado"))

@dataclass
class FiscalData:
    pgfn_listado: Optional[bool] = None
    valor_divida: Optional[float] = None
    tipo_divida: str = ""
    certidao_validada: bool = False
    evidence: Evidence = field(default_factory=lambda: Evidence("pgfn", "nao_consultado", "Não consultado"))

@dataclass
class JudicialData:
    total_processos: Optional[int] = None
    execucoes: Optional[int] = None
    trabalhistas: Optional[int] = None
    recuperacao_judicial_propria: bool = False
    recuperacao_extrajudicial_propria: bool = False
    como_credora_em_rj_terceiros: bool = False
    acoes_como_autora_cobranca: Optional[int] = None
    evidence: Evidence = field(default_factory=lambda: Evidence("tribunais", "nao_consultado", "Não consultado"))

@dataclass
class ReputationData:
    possui_site: bool = False
    possui_linkedin: bool = False
    possui_instagram: bool = False
    noticias_negativas: int = 0
    reclamacoes_publicas: int = 0
    crise_reputacional: bool = False
    evidence: Evidence = field(default_factory=lambda: Evidence("reputacao", "nao_consultado", "Não consultado"))

@dataclass
class SectorData:
    setor: str = ""
    risco_setorial: str = "medio"
    empresa_vs_setor: str = "dentro_da_media"
    uf: str = ""
    observacao: str = ""
    evidence: Evidence = field(default_factory=lambda: Evidence("setor", "nao_consultado", "Não consultado"))

@dataclass
class FinancialData:
    liquidez_corrente: Optional[float] = None
    endividamento: Optional[float] = None
    ebitda: Optional[float] = None
    margem_liquida: Optional[float] = None
    capital_giro: Optional[float] = None
    fluxo_caixa_negativo_recorrente: Optional[bool] = None
    fonte_publica_disponivel: bool = False
    evidence: Evidence = field(default_factory=lambda: Evidence("financeiro", "nao_consultado", "Não consultado"))

# =========================
# Adaptadores / Conectores
# =========================
class ReceitaAdapter:
    @staticmethod
    def consultar(cnpj: str) -> ReceitaData:
        # Tenta BrasilAPI primeiro, depois ReceitaWS como fallback
        for url in [
            f"https://brasilapi.com.br/api/cnpj/v1/{cnpj}",
            f"https://receitaws.com.br/v1/cnpj/{cnpj}",
        ]:
            try:
                r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
                if r.status_code != 200:
                    continue
                j = r.json()
                cnaes_sec = []
                for item in j.get("cnaes_secundarios", []) or []:
                    codigo = item.get("codigo") or ""
                    desc = item.get("descricao") or ""
                    cnaes_sec.append(f"{codigo} - {desc}".strip(" -"))
                return ReceitaData(
                    cnpj=cnpj,
                    razao_social=j.get("razao_social", "") or j.get("nome", ""),
                    nome_fantasia=j.get("nome_fantasia", ""),
                    situacao_cadastral=j.get("descricao_situacao_cadastral", "") or j.get("situacao", ""),
                    data_abertura=j.get("data_inicio_atividade", "") or j.get("abertura", ""),
                    natureza_juridica=j.get("natureza_juridica", ""),
                    cnae_principal=j.get("cnae_fiscal_descricao", "") or j.get("atividade_principal", [{}])[0].get("text", "") if j.get("atividade_principal") else "",
                    cnae_secundarios=cnaes_sec,
                    capital_social=apenas_numero(j.get("capital_social")),
                    porte=j.get("porte", "") or j.get("porte", ""),
                    uf=j.get("uf", "") or j.get("uf", ""),
                    municipio=j.get("municipio", "") or j.get("municipio", ""),
                    qsa=j.get("qsa", []) or [],
                    evidence=Evidence("receita", "confirmacao", f"Cadastro retornado: {url}", raw=j),
                )
            except Exception:
                continue
        return ReceitaData(
            cnpj=cnpj,
            evidence=Evidence("receita", "erro", "Todas as fontes de cadastro falharam")
        )

class PGFNAdapter:
    """
    Placeholder ativo — consulta pública PGFN.
    Quando a integração real for plugada, substituir o corpo deste método.
    A ausência de consulta NÃO equivale a regularidade (princípio de conservadorismo).
    """
    @staticmethod
    def consultar(cnpj: str) -> FiscalData:
        return FiscalData(
            pgfn_listado=None,
            valor_divida=None,
            certidao_validada=False,
            evidence=Evidence(
                "pgfn", "nao_consultado",
                "Consulta PGFN requer integração interna ou conferência documental. "
                "Ausência de consulta NÃO equivale a regularidade fiscal.",
            ),
        )

class DataJudAdapter:
    """
    Adaptador DataJud (API CNJ — gratuita).
    Endpoint: https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search
    Requer desbloqueio de rede corporativa para o domínio datajud.cnj.jus.br
    """
    ENDPOINT = "https://api-publica.datajud.cnj.jus.br/api_publica_tjsp/_search"
    API_KEY = "APIKey cDZHYzlZa0JadVREZDJCendFbXNpTDQxNDJ"  # chave pública CNJ

    @staticmethod
    def consultar(cnpj: str) -> JudicialData:
        payload = {
            "query": {
                "bool": {
                    "should": [
                        {"match": {"numeroProcesso": cnpj}},
                        {"match": {"partes.nome": cnpj}},
                    ]
                }
            },
            "size": 100,
        }
        try:
            r = requests.post(
                DataJudAdapter.ENDPOINT,
                json=payload,
                headers={**HEADERS, "Authorization": DataJudAdapter.API_KEY},
                timeout=TIMEOUT,
            )
            if r.status_code != 200:
                return JudicialData(
                    evidence=Evidence("tribunais", "nao_consultado",
                                      f"DataJud retornou HTTP {r.status_code}. Verifique acesso de rede.")
                )
            hits = r.json().get("hits", {}).get("hits", [])
            total = r.json().get("hits", {}).get("total", {}).get("value", 0)
            execucoes = sum(
                1 for h in hits
                if "execu" in str(h.get("_source", {}).get("classeProcessual", "")).lower()
            )
            trabalhistas = sum(
                1 for h in hits
                if "trabalh" in str(h.get("_source", {}).get("classeProcessual", "")).lower()
            )
            return JudicialData(
                total_processos=total,
                execucoes=execucoes,
                trabalhistas=trabalhistas,
                recuperacao_judicial_propria=any(
                    "recupera" in str(h.get("_source", {})).lower() for h in hits
                ),
                evidence=Evidence("tribunais", "confirmacao" if total > 0 else "ausencia",
                                  f"{total} processos localizados no DataJud (TJSP).", raw={"total": total}),
            )
        except Exception as e:
            return JudicialData(
                evidence=Evidence("tribunais", "erro", f"Falha no DataJud: {e}")
            )

class ReputationAdapter:
    @staticmethod
    def consultar(receita: ReceitaData) -> ReputationData:
        return ReputationData(
            evidence=Evidence(
                "reputacao", "nao_consultado",
                "Reputação digital não automatizada. Plugue conector de mídia/social.",
            ),
        )

class SectorAdapter:
    HIGH_RISK_TERMS = ["cobran", "constru", "transporte", "moda", "varejista", "factoring"]
    LOW_RISK_TERMS = ["energia", "saneamento", "farmac", "alimentos", "saude", "educac"]

    @staticmethod
    def consultar(receita: ReceitaData) -> SectorData:
        desc = (receita.cnae_principal or "").lower()
        risco = "medio"
        if any(t in desc for t in SectorAdapter.HIGH_RISK_TERMS):
            risco = "medio_alto"
        if any(t in desc for t in SectorAdapter.LOW_RISK_TERMS):
            risco = "baixo"
        return SectorData(
            setor=receita.cnae_principal or "Não classificado",
            risco_setorial=risco,
            uf=receita.uf,
            observacao="Classificação heurística por CNAE. Substitua por benchmark por CNAE+UF.",
            evidence=Evidence("setor", "indicio", "Setor inferido do CNAE principal",
                              raw={"cnae": receita.cnae_principal}),
        )

class FinancialAdapter:
    @staticmethod
    def consultar(cnpj: str) -> FinancialData:
        return FinancialData(
            fonte_publica_disponivel=False,
            evidence=Evidence(
                "financeiro", "nao_consultado",
                "Sem balanço/balancete conectado. Plugue ERP, DRE ou balancete.",
            ),
        )

# =========================
# Motor de Score — integridade total preservada
# =========================
class ScoreEngine:
    @staticmethod
    def score_receita(receita: ReceitaData) -> Tuple[float, List[str], List[str]]:
        pontos = 0.0
        greens, yellows = [], []
        if receita.evidence.status == "confirmacao":
            greens.append("Cadastro empresarial confirmado em fonte aberta")
            pontos += 8
        anos = years_since(receita.data_abertura)
        if anos is not None:
            if anos >= 10:
                pontos += 8; greens.append(f"Tempo de mercado robusto: {anos:.1f} anos")
            elif anos >= 3:
                pontos += 4; greens.append(f"Tempo de mercado aceitável: {anos:.1f} anos")
            else:
                pontos -= 4; yellows.append(f"Empresa ainda jovem: {anos:.1f} anos")
        if receita.situacao_cadastral:
            if "ativa" in receita.situacao_cadastral.lower():
                pontos += 8; greens.append("Situação cadastral ativa")
            else:
                pontos -= 15; yellows.append(f"Situação cadastral exige atenção: {receita.situacao_cadastral}")
        else:
            pontos -= 8; yellows.append("Situação cadastral não confirmada")
        if receita.capital_social > 0:
            greens.append(f"Capital social informado: R$ {receita.capital_social:,.2f}")
            pontos += 2
        if not receita.qsa:
            yellows.append("Quadro societário não confirmado"); pontos -= 2
        return pontos, greens, yellows

    @staticmethod
    def score_fiscal(fiscal: FiscalData) -> Tuple[float, List[str], List[str], List[str]]:
        pontos, greens, yellows, reds = 0.0, [], [], []
        if fiscal.evidence.status in {"nao_consultado", "ausencia"}:
            yellows.append("PGFN/Certidão não validada automaticamente"); pontos -= 5
        elif fiscal.pgfn_listado is True:
            reds.append("Empresa listada em dívida ativa/indício fiscal relevante"); pontos -= 20
        elif fiscal.pgfn_listado is False:
            greens.append("Sem listagem positiva no conector fiscal"); pontos += 4
        if fiscal.certidao_validada:
            greens.append("Certidão fiscal validada"); pontos += 8
        return pontos, greens, yellows, reds

    @staticmethod
    def score_judicial(jud: JudicialData) -> Tuple[float, List[str], List[str], List[str], List[str]]:
        pontos, greens, yellows, reds, sinais_rj = 0.0, [], [], [], []
        if jud.evidence.status == "nao_consultado":
            yellows.append("Base judicial não conectada"); pontos -= 6
        if jud.recuperacao_judicial_propria:
            reds.append("Recuperação judicial própria identificada")
            sinais_rj.append("Recuperação judicial própria"); pontos -= 45
        if jud.recuperacao_extrajudicial_propria:
            reds.append("Recuperação extrajudicial própria identificada")
            sinais_rj.append("Recuperação extrajudicial própria"); pontos -= 35
        if jud.como_credora_em_rj_terceiros:
            yellows.append("Empresa aparece como credora em RJ de terceiros")
            sinais_rj.append("Exposição indireta a RJ de terceiros"); pontos -= 8
        if jud.total_processos is not None:
            if jud.total_processos >= 100:
                yellows.append(f"Contencioso elevado: {jud.total_processos} processos"); pontos -= 10
            elif jud.total_processos >= 20:
                yellows.append(f"Contencioso moderado: {jud.total_processos} processos"); pontos -= 5
            else:
                greens.append("Volume processual baixo"); pontos += 3
        if jud.execucoes:
            if jud.execucoes >= 10:
                reds.append(f"Execuções relevantes: {jud.execucoes}"); pontos -= 12
            elif jud.execucoes > 0:
                yellows.append(f"Execuções identificadas: {jud.execucoes}"); pontos -= 5
        return pontos, greens, yellows, reds, sinais_rj

    @staticmethod
    def score_reputacao(rep: ReputationData) -> Tuple[float, List[str], List[str], List[str]]:
        pontos, greens, yellows, reds = 0.0, [], [], []
        if rep.evidence.status == "nao_consultado":
            yellows.append("Reputação digital não automatizada"); pontos -= 4
        presencas = sum([rep.possui_site, rep.possui_linkedin, rep.possui_instagram])
        if presencas >= 2:
            greens.append("Presença digital consistente"); pontos += 4
        elif presencas == 1:
            greens.append("Presença digital básica"); pontos += 2
        if rep.noticias_negativas >= 5 or rep.crise_reputacional:
            reds.append("Sinal reputacional crítico"); pontos -= 15
        elif rep.noticias_negativas >= 1 or rep.reclamacoes_publicas >= 20:
            yellows.append("Sinais reputacionais relevantes"); pontos -= 6
        return pontos, greens, yellows, reds

    @staticmethod
    def score_setor(setor: SectorData) -> Tuple[float, List[str], List[str]]:
        pontos, greens, yellows = 0.0, [], []
        mapa = {"baixo": (8, greens, "baixo"), "medio": (2, greens, "moderado"),
                "medio_alto": (-6, yellows, "médio-alto"), "alto": (-10, yellows, "alto")}
        pts, lista, label = mapa.get(setor.risco_setorial, (-4, yellows, "indefinido"))
        pontos += pts
        lista.append(f"Setor com risco estrutural {label}")
        return pontos, greens, yellows

    @staticmethod
    def score_financeiro(fin: FinancialData) -> Tuple[float, List[str], List[str], List[str], List[str]]:
        pontos, greens, yellows, reds, sinais_rj = 0.0, [], [], [], []
        if not fin.fonte_publica_disponivel:
            yellows.append("Sem demonstrações financeiras conectadas"); pontos -= 8
            return pontos, greens, yellows, reds, sinais_rj
        if fin.liquidez_corrente is not None:
            if fin.liquidez_corrente >= 1.5:
                greens.append(f"Liquidez corrente saudável: {fin.liquidez_corrente:.2f}"); pontos += 8
            elif fin.liquidez_corrente >= 1.0:
                greens.append(f"Liquidez corrente aceitável: {fin.liquidez_corrente:.2f}"); pontos += 3
            else:
                reds.append(f"Liquidez corrente pressionada: {fin.liquidez_corrente:.2f}")
                sinais_rj.append("Liquidez corrente abaixo de 1,0"); pontos -= 12
        if fin.margem_liquida is not None:
            if fin.margem_liquida < 0:
                reds.append(f"Margem líquida negativa: {fin.margem_liquida:.2%}")
                sinais_rj.append("Margem líquida negativa"); pontos -= 10
            elif fin.margem_liquida < 0.03:
                yellows.append(f"Margem líquida apertada: {fin.margem_liquida:.2%}"); pontos -= 4
            else:
                greens.append(f"Margem líquida positiva: {fin.margem_liquida:.2%}"); pontos += 4
        if fin.fluxo_caixa_negativo_recorrente is True:
            reds.append("Fluxo de caixa negativo recorrente")
            sinais_rj.append("Fluxo de caixa negativo recorrente"); pontos -= 14
        return pontos, greens, yellows, reds, sinais_rj

    @staticmethod
    def score_global(receita, fiscal, jud, rep, setor, fin) -> dict:
        base = 50.0
        memoria = {"base": base}
        red_flags, yellow_flags, green_flags, sinais_rj = [], [], [], []

        pr, g1, y1 = ScoreEngine.score_receita(receita)
        pf, g2, y2, r2 = ScoreEngine.score_fiscal(fiscal)
        pj, g3, y3, r3, s3 = ScoreEngine.score_judicial(jud)
        pp, g4, y4, r4 = ScoreEngine.score_reputacao(rep)
        ps, g5, y5 = ScoreEngine.score_setor(setor)
        pfin, g6, y6, r6, s6 = ScoreEngine.score_financeiro(fin)

        memoria.update({"receita": pr, "fiscal": pf, "judicial": pj,
                        "reputacao": pp, "setor": ps, "financeiro": pfin})

        green_flags.extend(g1+g2+g3+g4+g5+g6)
        yellow_flags.extend(y1+y2+y3+y4+y5+y6)
        red_flags.extend(r2+r3+r4+r6)
        sinais_rj.extend(s3+s6)

        score = int(round(clamp(base+pr+pf+pj+pp+ps+pfin, 0, 100)))
        pd_val = round(clamp(60 - (score * 0.55), 1, 80), 1)

        def to_rating(s):
            for thresh, r in [(90,"AAA"),(82,"AA"),(74,"A"),(66,"BBB"),(58,"BB"),(48,"B"),(36,"C")]:
                if s >= thresh: return r
            return "D"

        def to_risco(s):
            return "baixo" if s >= 75 else "medio" if s >= 50 else "alto"

        def recomendacao(s, reds, yellows):
            if s >= 75:
                return ("Limite padrão ou escalonado acima da média", "28 a 35 dias",
                        ["sem garantia pesada em tickets usuais", "cessão de recebíveis para volumes maiores"],
                        "monitoramento trimestral com gatilho mensal para fiscal/judicial")
            if s >= 50:
                return ("Limite conservador e escalonado por performance", "14 a 28 dias",
                        ["aval", "cessão de recebíveis", "reforço contratual"],
                        "monitoramento mensal")
            return ("Limite reduzido ou operação pontual", "7 a 14 dias",
                    ["pagamento antecipado parcial", "garantia real ou fidejussória", "seguro de crédito"],
                    "monitoramento semanal/mensal com gatilhos imediatos de bloqueio")

        rating = to_rating(score)
        risco = to_risco(score)
        limite, prazo, garantias, monitoramento = recomendacao(score, red_flags, yellow_flags)

        resumo = [
            f"Empresa analisada: {receita.razao_social or 'Não identificado'}",
            f"Score final: {score} | Rating: {rating} | PD estimada: {pd_val:.1f}%",
            f"Classificação de risco: {risco}",
        ]
        if sinais_rj:
            resumo.append("Sinais de stress/RJ: " + "; ".join(sorted(set(sinais_rj))))
        if not fin.fonte_publica_disponivel:
            resumo.append("Sem dados financeiros conectados — avaliação financeira conservadora.")
        if fiscal.evidence.status == "nao_consultado":
            resumo.append("Regularidade fiscal exige validação documental antes da aprovação.")
        if jud.evidence.status == "nao_consultado":
            resumo.append("Base judicial não conectada — risco jurídico pode estar subavaliado.")

        return {
            "cnpj": receita.cnpj,
            "empresa": receita.razao_social,
            "score": score,
            "rating": rating,
            "pd": pd_val,
            "classificacao_risco": risco,
            "limite_sugerido": limite,
            "prazo_sugerido": prazo,
            "garantias_recomendadas": garantias,
            "plano_monitoramento": monitoramento,
            "sinais_rj": sorted(set(sinais_rj)),
            "red_flags": sorted(set(red_flags)),
            "yellow_flags": sorted(set(yellow_flags)),
            "green_flags": sorted(set(green_flags)),
            "resumo_executivo": resumo,
            "memoria_calculo": memoria,
            "conectores": {
                "receita": {"status": receita.evidence.status, "summary": receita.evidence.summary},
                "fiscal": {"status": fiscal.evidence.status, "summary": fiscal.evidence.summary},
                "judicial": {"status": jud.evidence.status, "summary": jud.evidence.summary},
                "reputacao": {"status": rep.evidence.status, "summary": rep.evidence.summary},
                "setor": {"status": setor.evidence.status, "summary": setor.evidence.summary},
                "financeiro": {"status": fin.evidence.status, "summary": fin.evidence.summary},
            },
            "dados": {
                "receita": asdict(receita),
                "fiscal": asdict(fiscal),
                "judicial": asdict(jud),
                "reputacao": asdict(rep),
                "setor": asdict(setor),
                "financeiro": asdict(fin),
            },
            "analisado_em": dt.datetime.now().isoformat(),
        }

# =========================
# Orquestração
# =========================
def analisar_cnpj(cnpj: str) -> dict:
    cnpj = limpar_cnpj(cnpj)
    if not validar_cnpj(cnpj):
        raise ValueError(f"CNPJ inválido: {cnpj}")
    receita = ReceitaAdapter.consultar(cnpj)
    fiscal = PGFNAdapter.consultar(cnpj)
    judicial = DataJudAdapter.consultar(cnpj)
    reputacao = ReputationAdapter.consultar(receita)
    setor = SectorAdapter.consultar(receita)
    financeiro = FinancialAdapter.consultar(cnpj)
    return ScoreEngine.score_global(receita, fiscal, judicial, reputacao, setor, financeiro)

# =========================
# Geração de PDF
# =========================
def gerar_pdf(resultado: dict) -> bytes:
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4,
                            leftMargin=1.6*cm, rightMargin=1.6*cm,
                            topMargin=1.4*cm, bottomMargin=1.4*cm)
    styles = getSampleStyleSheet()
    body = ParagraphStyle("Body", parent=styles["BodyText"], leading=14, fontSize=9)
    elements = []
    elements.append(Paragraph(f"CreditLens — Análise de Crédito", styles["Title"]))
    elements.append(Paragraph(f"{resultado.get('empresa', '')} | CNPJ: {resultado.get('cnpj', '')}", styles["Heading2"]))
    elements.append(Spacer(1, 8))
    resumo_rows = [
        ["Score", str(resultado.get("score", ""))],
        ["Rating", resultado.get("rating", "")],
        ["PD Estimada", f"{resultado.get('pd', 0):.1f}%"],
        ["Risco", resultado.get("classificacao_risco", "")],
        ["Limite sugerido", resultado.get("limite_sugerido", "")],
        ["Prazo sugerido", resultado.get("prazo_sugerido", "")],
        ["Monitoramento", resultado.get("plano_monitoramento", "")],
        ["Analisado em", resultado.get("analisado_em", "")[:19]],
    ]
    t = Table(resumo_rows, colWidths=[4.5*cm, 11.5*cm])
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.3, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    elements.append(t)
    elements.append(Spacer(1, 10))
    for titulo, items in [
        ("Resumo Executivo", resultado.get("resumo_executivo", [])),
        ("Green Flags", resultado.get("green_flags", [])),
        ("Yellow Flags", resultado.get("yellow_flags", [])),
        ("Red Flags", resultado.get("red_flags", [])),
        ("Sinais de Stress / RJ", resultado.get("sinais_rj", [])),
        ("Garantias Recomendadas", resultado.get("garantias_recomendadas", [])),
    ]:
        elements.append(Paragraph(titulo, styles["Heading2"]))
        if not items:
            elements.append(Paragraph("• Sem apontamentos relevantes.", body))
        else:
            for item in items:
                elements.append(Paragraph(f"• {item}", body))
        elements.append(Spacer(1, 6))
    doc.build(elements)
    return buffer.getvalue()

# =========================
# Rotas da API
# =========================
class CNPJRequest(BaseModel):
    cnpj: str

@app.get("/")
def root():
    return {"status": "ok", "app": "CreditLens API", "version": "2.0.0"}

@app.get("/health")
def health():
    return {"status": "healthy", "timestamp": dt.datetime.now().isoformat()}

@app.post("/api/analisar")
def analisar(req: CNPJRequest):
    """Análise pontual de um CNPJ em tempo real."""
    try:
        resultado = analisar_cnpj(req.cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

@app.get("/api/analisar/{cnpj}")
def analisar_get(cnpj: str):
    """Análise pontual via GET (útil para testes rápidos)."""
    try:
        resultado = analisar_cnpj(cnpj)
        return JSONResponse(content=resultado)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro interno: {e}")

@app.get("/api/pdf/{cnpj}")
def baixar_pdf(cnpj: str):
    """Gera e retorna PDF da análise."""
    try:
        resultado = analisar_cnpj(cnpj)
        pdf_bytes = gerar_pdf(resultado)
        return JSONResponse(content={
            "pdf_base64": __import__("base64").b64encode(pdf_bytes).decode(),
            "filename": f"analise_{limpar_cnpj(cnpj)}.pdf"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/lote")
async def processar_lote(file: UploadFile = File(...)):
    """Processa lote de CNPJs via Excel. Coluna obrigatória: cnpj"""
    try:
        contents = await file.read()
        df = pd.read_excel(io.BytesIO(contents))
        if "cnpj" not in df.columns:
            raise HTTPException(status_code=422, detail="Planilha precisa ter coluna 'cnpj'.")
        cnpjs = [limpar_cnpj(str(v)) for v in df["cnpj"].dropna().tolist()]
        resultados = []
        erros = []
        for cnpj in cnpjs[:200]:  # limite de segurança
            try:
                r = analisar_cnpj(cnpj)
                resultados.append(r)
            except Exception as e:
                erros.append({"cnpj": cnpj, "erro": str(e)})
        return JSONResponse(content={
            "processados": len(resultados),
            "erros": len(erros),
            "resultados": resultados,
            "erros_detalhe": erros,
        })
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/conectores")
def status_conectores():
    """Retorna status dos conectores configurados."""
    return {
        "receita": {"nome": "BrasilAPI / ReceitaWS", "status": "ativo", "tipo": "api_publica"},
        "pgfn": {"nome": "PGFN / Dívida Ativa", "status": "pendente", "tipo": "placeholder"},
        "judicial": {"nome": "DataJud / CNJ", "status": "ativo_parcial", "tipo": "api_publica"},
        "reputacao": {"nome": "Reputação Digital", "status": "pendente", "tipo": "placeholder"},
        "financeiro": {"nome": "Balanço / ERP", "status": "pendente", "tipo": "placeholder"},
        "setor": {"nome": "Classificação Setorial CNAE", "status": "ativo", "tipo": "heuristica"},
    }
