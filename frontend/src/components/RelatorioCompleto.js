// src/components/RelatorioCompleto.js — P.I.L.D.E.R™ v2.0
// Framework: CONFIRMAÇÃO | EVIDÊNCIA | INDÍCIO | AUSÊNCIA

const NAVY = "#1E3A5F";
const GOLD = "#b49303";
const BG = "#f5f0e8";
const CARD = "#ffffff";
const BORDER = "#d4c9a8";
const MUTED = "#6b6b7b";
const TEXT = "#1a1a2e";

// Cores do framework de evidência
const EVIDENCIA_CONFIG = {
  CONFIRMACAO: { label: "CONFIRMAÇÃO", cor: "#0e7a5a", bg: "#edfaf5", icone: "✅", desc: "Fonte primária oficial" },
  EVIDENCIA:   { label: "EVIDÊNCIA",   cor: "#16a34a", bg: "#f0fdf4", icone: "🟢", desc: "Fonte confiável" },
  INDICIO:     { label: "INDÍCIO",     cor: "#b45309", bg: "#fff8ee", icone: "🟡", desc: "Probabilidade relevante" },
  AUSENCIA:    { label: "AUSÊNCIA",    cor: "#6b7280", bg: "#f9fafb", icone: "⚪", desc: "Não encontrado — não equivale a regularidade" },
  ALERTA:      { label: "ALERTA",      cor: "#c0392b", bg: "#fff0ee", icone: "🔴", desc: "Evidência negativa confirmada" },
};

const CONFIANCA_COLOR = { Alto: "#0e7a5a", Médio: "#b45309", Baixo: "#c0392b" };
const INTENSIDADE_COLOR = {
  "CRÍTICO": "#7f1d1d", "ALTO": "#c0392b", "MÉDIO": "#b45309",
  "BAIXO": "#0e7a5a", "NÃO IDENTIFICADO": "#9ca3af"
};

function EvidenciaBadge({ categoria }) {
  const cfg = EVIDENCIA_CONFIG[categoria] || EVIDENCIA_CONFIG.AUSENCIA;
  return (
    <span style={{
      background: cfg.bg, color: cfg.cor,
      border: `1px solid ${cfg.cor}44`,
      borderRadius: 20, padding: "2px 10px",
      fontSize: 10, fontWeight: 800,
      letterSpacing: 0.5, whiteSpace: "nowrap",
    }}>
      {cfg.icone} {cfg.label}
    </span>
  );
}

function ConfiancaBadge({ nivel }) {
  const color = CONFIANCA_COLOR[nivel] || "#9ca3af";
  return (
    <span style={{
      background: `${color}18`, color,
      border: `1px solid ${color}33`,
      borderRadius: 6, padding: "2px 8px",
      fontSize: 10, fontWeight: 700,
    }}>
      Confiança: {nivel}
    </span>
  );
}

function BlocoConfianca({ blocos }) {
  if (!blocos) return null;
  return (
    <div style={{
      background: CARD, border: `1px solid ${BORDER}`,
      borderRadius: 12, padding: 18, marginBottom: 14,
    }}>
      <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
        textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 12 }}>
        Nível de Confiança por Bloco
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8 }}>
        {Object.entries(blocos).map(([bloco, nivel]) => (
          <div key={bloco} style={{
            background: BG, border: `1px solid ${BORDER}`,
            borderRadius: 8, padding: "8px 12px", textAlign: "center",
          }}>
            <div style={{ fontSize: 10, color: MUTED, textTransform: "capitalize",
              marginBottom: 4 }}>{bloco}</div>
            <div style={{ fontSize: 13, fontWeight: 800,
              color: CONFIANCA_COLOR[nivel] || "#9ca3af" }}>{nivel}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function RastreabilidadeSummary({ rastreio }) {
  if (!rastreio) return null;
  const r = rastreio.rastreabilidade || {};
  return (
    <div style={{
      background: NAVY, borderRadius: 12, padding: 18, marginBottom: 14,
    }}>
      <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
        textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 12 }}>
        Rastreabilidade — Auditoria P.I.L.D.E.R™
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(4,1fr)", gap: 8, marginBottom: 12 }}>
        {[
          { l: "Total Fontes", v: r.total_fontes || 0, c: "#e2e8f0" },
          { l: "Confirmadas", v: r.fontes_confirmadas || 0, c: "#34d399" },
          { l: "Ausências", v: r.fontes_ausencia || 0, c: "#94a3b8" },
          { l: "Alertas", v: r.fontes_alerta || 0, c: "#f87171" },
        ].map(({ l, v, c }) => (
          <div key={l} style={{ background: "#ffffff11", borderRadius: 8, padding: "8px 12px", textAlign: "center" }}>
            <div style={{ fontSize: 10, color: "#94a3b8", marginBottom: 3 }}>{l}</div>
            <div style={{ fontSize: 22, fontWeight: 800, color: c, fontFamily: "monospace" }}>{v}</div>
          </div>
        ))}
      </div>
      {rastreio.id_analise && (
        <div style={{ fontSize: 10, color: "#475569", fontFamily: "monospace" }}>
          ID: {rastreio.id_analise} | {rastreio.data_hora?.slice(0,19)}
        </div>
      )}
    </div>
  );
}

function FontesClassificadas({ fontes }) {
  const [filtro, setFiltro] = React.useState("TODAS");
  if (!fontes?.length) return null;

  const categorias = ["TODAS", "CONFIRMACAO", "EVIDENCIA", "INDICIO", "AUSENCIA", "ALERTA"];
  const filtradas = filtro === "TODAS" ? fontes : fontes.filter(f => f.categoria_evidencia === filtro);

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 14, overflow: "hidden", marginBottom: 14 }}>
      <div style={{ background: NAVY, padding: "14px 18px", display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>
            Fontes Classificadas — Framework de Evidência
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
            CONFIRMAÇÃO | EVIDÊNCIA | INDÍCIO | AUSÊNCIA
          </div>
        </div>
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap" }}>
          {categorias.map(cat => {
            const cfg = cat === "TODAS" ? { icone: "📋", label: "Todas", cor: "#94a3b8" } : (EVIDENCIA_CONFIG[cat] || {});
            return (
              <button key={cat} onClick={() => setFiltro(cat)} style={{
                background: filtro === cat ? "#ffffff22" : "transparent",
                border: filtro === cat ? "1px solid #ffffff44" : "1px solid transparent",
                color: filtro === cat ? "#fff" : "#64748b",
                borderRadius: 6, padding: "3px 8px",
                fontSize: 10, cursor: "pointer", fontWeight: 600,
              }}>
                {cfg.icone} {cfg.label || cat}
              </button>
            );
          })}
        </div>
      </div>

      {filtradas.map((f, i) => {
        const cfg = EVIDENCIA_CONFIG[f.categoria_evidencia] || EVIDENCIA_CONFIG.AUSENCIA;
        const pts = f.pontos || 0;
        return (
          <div key={i} style={{
            display: "flex", alignItems: "center", gap: 10,
            padding: "10px 16px", borderBottom: `1px solid ${BORDER}`,
            background: i % 2 === 0 ? CARD : BG,
          }}>
            <span style={{ fontSize: 10, color: MUTED, minWidth: 20, fontFamily: "monospace" }}>{i+1}</span>
            <span style={{ flex: 1, fontSize: 12, color: TEXT, fontWeight: 500 }}>
              {f.fonte}
              {f.resumo && (
                <span style={{ fontSize: 11, color: MUTED, display: "block", marginTop: 2 }}>
                  {f.resumo?.slice(0, 120)}
                </span>
              )}
            </span>
            <EvidenciaBadge categoria={f.categoria_evidencia} />
            <span style={{
              fontSize: 12, fontFamily: "monospace", fontWeight: 700,
              color: pts > 0 ? "#0e7a5a" : pts < 0 ? "#c0392b" : MUTED,
              minWidth: 36, textAlign: "right",
            }}>
              {pts > 0 ? `+${pts}` : pts}
            </span>
          </div>
        );
      })}
    </div>
  );
}

function PareceiroSenior({ parecer }) {
  if (!parecer?.parecer_completo) return null;
  const [expandido, setExpandido] = React.useState(true);

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 14, overflow: "hidden", marginBottom: 14 }}>
      <div style={{
        background: NAVY, padding: "14px 18px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        cursor: "pointer",
      }} onClick={() => setExpandido(e => !e)}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 700, color: "#fff" }}>
            📋 Parecer Executivo — Analista Sênior P.I.L.D.E.R™
          </div>
          <div style={{ fontSize: 10, color: "#94a3b8", marginTop: 2 }}>
            {parecer.via_ia ? "✨ Gerado via Inteligência Artificial" : "⚙ Gerado por regras estruturadas"}
          </div>
        </div>
        <span style={{ color: "#94a3b8", fontSize: 18 }}>{expandido ? "▲" : "▼"}</span>
      </div>
      {expandido && (
        <div style={{ padding: 20 }}>
          <div style={{
            fontSize: 12, color: TEXT, lineHeight: 1.9,
            whiteSpace: "pre-wrap", fontFamily: "'IBM Plex Mono', monospace",
            background: BG, borderRadius: 8, padding: 16,
            border: `1px solid ${BORDER}`,
            maxHeight: 600, overflowY: "auto",
          }}>
            {parecer.parecer_completo}
          </div>
        </div>
      )}
    </div>
  );
}

function GovernancaPILDER({ rastreio }) {
  if (!rastreio?.governo_pilder) return null;
  const letras = [
    { l: "P", cor: "#c0392b" }, { l: "I", cor: "#1E3A5F" },
    { l: "L", cor: "#b45309" }, { l: "D", cor: "#0e7a5a" },
    { l: "E", cor: "#6d28d9" }, { l: "R", cor: "#b49303" },
  ];
  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 12, padding: 18, marginBottom: 14 }}>
      <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
        textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 12 }}>
        Governança P.I.L.D.E.R™ — Esta Análise
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {Object.entries(rastreio.governo_pilder).map(([letra, desc], i) => {
          const cfg = letras[i] || { l: letra, cor: NAVY };
          return (
            <div key={letra} style={{ display: "flex", alignItems: "center", gap: 12 }}>
              <div style={{
                width: 32, height: 32, borderRadius: 8, flexShrink: 0,
                background: `${cfg.cor}18`, border: `2px solid ${cfg.cor}44`,
                display: "flex", alignItems: "center", justifyContent: "center",
                fontSize: 16, fontWeight: 900, color: cfg.cor,
                fontFamily: "Georgia, serif",
              }}>{letra[0]}</div>
              <div style={{ fontSize: 12, color: TEXT }}>
                <b style={{ color: cfg.cor }}>{letra}</b> — {desc}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Import React para hooks
import React, { useState } from "react";

export default function RelatorioCompleto({ resultado }) {
  if (!resultado) return null;

  const parecer = resultado.parecer_senior;
  const rastreio = resultado.rastreabilidade;
  const bal = resultado.balanco_detalhado;
  const cisp = resultado.cisp_detalhado;

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>

      {/* Legenda do framework */}
      <div style={{
        background: CARD, border: `1px solid ${BORDER}`,
        borderRadius: 12, padding: 16,
      }}>
        <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
          textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 10 }}>
          Framework de Evidência P.I.L.D.E.R™
        </div>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {Object.entries(EVIDENCIA_CONFIG).map(([k, v]) => (
            <div key={k} style={{
              background: v.bg, border: `1px solid ${v.cor}44`,
              borderRadius: 8, padding: "6px 12px",
            }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: v.cor }}>
                {v.icone} {v.label}
              </div>
              <div style={{ fontSize: 10, color: MUTED, marginTop: 2 }}>{v.desc}</div>
            </div>
          ))}
        </div>
      </div>

      {/* Rastreabilidade */}
      <RastreabilidadeSummary rastreio={rastreio} />

      {/* Confiança por bloco */}
      <BlocoConfianca blocos={parecer?.blocos_confianca} />

      {/* Parecer sênior */}
      <PareceiroSenior parecer={parecer} />

      {/* Fontes classificadas */}
      <FontesClassificadas fontes={parecer?.fontes_classificadas} />

      {/* Balanço */}
      {bal?.disponivel && (
        <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
            textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 10 }}>
            📊 Balanço / DRE — Parecer do Gestor
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 12 }}>
            {bal.red_flags?.length > 0 && (
              <div style={{ background: "#fff0ee", border: "1px solid #f5c6c6", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 10, color: "#c0392b", fontWeight: 700, marginBottom: 6 }}>🔴 RED FLAGS</div>
                {bal.red_flags.map((f, i) => <div key={i} style={{ fontSize: 11, color: "#7f1d1d", marginBottom: 3 }}>{f}</div>)}
              </div>
            )}
            {bal.yellow_flags?.length > 0 && (
              <div style={{ background: "#fff8ee", border: "1px solid #f59e0b33", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 10, color: "#b45309", fontWeight: 700, marginBottom: 6 }}>🟡 YELLOW FLAGS</div>
                {bal.yellow_flags.map((f, i) => <div key={i} style={{ fontSize: 11, color: "#7c2d12", marginBottom: 3 }}>{f}</div>)}
              </div>
            )}
            {bal.green_flags?.length > 0 && (
              <div style={{ background: "#edfaf5", border: "1px solid #a7f3d0", borderRadius: 8, padding: 12 }}>
                <div style={{ fontSize: 10, color: "#0e7a5a", fontWeight: 700, marginBottom: 6 }}>🟢 GREEN FLAGS</div>
                {bal.green_flags.map((f, i) => <div key={i} style={{ fontSize: 11, color: "#064e3b", marginBottom: 3 }}>{f}</div>)}
              </div>
            )}
          </div>
          {bal.parecer_gestor && (
            <div style={{
              background: BG, border: `1px solid ${BORDER}`, borderRadius: 8,
              padding: 14, fontSize: 11, color: TEXT, lineHeight: 1.8,
              whiteSpace: "pre-wrap", fontFamily: "monospace",
              maxHeight: 300, overflowY: "auto",
            }}>
              {bal.parecer_gestor}
            </div>
          )}
        </div>
      )}

      {/* CISP */}
      {cisp?.disponivel && (
        <div style={{ background: CARD, border: `1px solid ${BORDER}`, borderRadius: 12, padding: 18 }}>
          <div style={{ fontSize: 11, color: GOLD, fontWeight: 800,
            textTransform: "uppercase", letterSpacing: 1.2, marginBottom: 10 }}>
            📋 Ficha CISP — Comportamento Interno
          </div>
          <div style={{
            background: BG, border: `1px solid ${BORDER}`, borderRadius: 8,
            padding: 14, fontSize: 11, color: TEXT, lineHeight: 1.8,
            whiteSpace: "pre-wrap", fontFamily: "monospace",
            maxHeight: 250, overflowY: "auto",
          }}>
            {cisp.parecer_gestor}
          </div>
        </div>
      )}

      {/* Governança PILDER */}
      <GovernancaPILDER rastreio={rastreio} />

      {/* Assinatura */}
      <div style={{ textAlign: "center", padding: "12px 0",
        fontSize: 11, color: MUTED, fontWeight: 600, letterSpacing: 1 }}>
        P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito
      </div>
    </div>
  );
}
