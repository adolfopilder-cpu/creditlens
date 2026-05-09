// src/components/RelatorioFinanceiro.js — P.I.L.D.E.R™
// SEMPRE renderiza — mostra análise completa ou aviso detalhado quando sem documentos
import { useState } from "react";

const NAVY = "#1E3A5F";
const GOLD = "#b49303";
const BG = "#f5f0e8";
const CARD = "#ffffff";
const BORDER = "#d4c9a8";
const MUTED = "#6b6b7b";
const TEXT = "#1a1a2e";

function fmt(v, tipo = "moeda") {
  if (v == null || v === 0) return "—";
  if (tipo === "moeda") return `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 0 })}`;
  if (tipo === "pct") return `${Number(v).toFixed(1)}%`;
  if (tipo === "mult") return `${Number(v).toFixed(2)}×`;
  return String(v);
}

function Secao({ titulo, cor = NAVY, children }) {
  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{
        fontSize: 10, fontWeight: 800, color: cor,
        letterSpacing: 1.5, textTransform: "uppercase",
        borderBottom: `2px solid ${cor}22`, paddingBottom: 5, marginBottom: 10,
      }}>{titulo}</div>
      {children}
    </div>
  );
}

function Linha({ label, valor, classif, corClass }) {
  return (
    <div style={{
      display: "flex", justifyContent: "space-between", alignItems: "center",
      padding: "7px 12px", borderBottom: `1px solid ${BORDER}`,
      background: CARD,
    }}>
      <span style={{ fontSize: 12, color: TEXT }}>{label}</span>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 700, color: NAVY, fontFamily: "monospace" }}>{valor}</span>
        {classif && (
          <span style={{
            fontSize: 10, fontWeight: 700, color: corClass || MUTED,
            background: `${corClass || MUTED}18`,
            border: `1px solid ${corClass || MUTED}33`,
            borderRadius: 20, padding: "1px 8px", whiteSpace: "nowrap",
          }}>{classif}</span>
        )}
      </div>
    </div>
  );
}

function FlagBlock({ titulo, items, cor, bg, vazio }) {
  return (
    <div style={{
      background: bg, border: `1px solid ${cor}33`,
      borderRadius: 10, padding: 14,
    }}>
      <div style={{ fontSize: 11, fontWeight: 800, color: cor,
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
        {titulo} {items?.length > 0 ? `(${items.length})` : ""}
      </div>
      {!items?.length
        ? <div style={{ fontSize: 11, color: MUTED, fontStyle: "italic" }}>{vazio || "Nenhum"}</div>
        : items.map((f, i) => (
          <div key={i} style={{
            fontSize: 11, color: TEXT, marginBottom: 5,
            paddingLeft: 10, borderLeft: `3px solid ${cor}66`, lineHeight: 1.5,
          }}>{f}</div>
        ))
      }
    </div>
  );
}

function AgingBar({ indicadores, debito }) {
  if (!debito) return null;
  const faixas = [
    { label: "+5 dias", key: "vencido_5d", limite: 20 },
    { label: "+15 dias", key: "vencido_15d", limite: 15 },
    { label: "+30 dias", key: "vencido_30d", limite: 10 },
  ].filter(f => indicadores[f.key]);
  if (!faixas.length) return null;

  return (
    <div style={{ background: BG, borderRadius: 8, padding: 14, marginTop: 10 }}>
      <div style={{ fontSize: 10, color: MUTED, fontWeight: 700,
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 10 }}>
        Aging — Exposição por Faixa
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "flex-end", height: 80, marginBottom: 8 }}>
        {/* Barra do débito total */}
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
          <div style={{ background: NAVY, borderRadius: "4px 4px 0 0", width: "100%", height: 80,
            display: "flex", alignItems: "flex-end", justifyContent: "center", paddingBottom: 4 }}>
            <span style={{ color: "#fff", fontSize: 10, fontWeight: 700 }}>
              {(debito/1e6).toFixed(1)}mi
            </span>
          </div>
          <div style={{ fontSize: 9, color: MUTED, marginTop: 4 }}>Total</div>
        </div>
        {faixas.map(({ label, key, limite }) => {
          const val = indicadores[key];
          const pct = val / debito;
          const cor = pct >= limite/100 * 2 ? "#c0392b" : pct >= limite/100 ? "#b45309" : "#0e7a5a";
          return (
            <div key={key} style={{ display: "flex", flexDirection: "column", alignItems: "center", flex: 1 }}>
              <div style={{
                background: cor, borderRadius: "4px 4px 0 0", width: "100%",
                height: `${Math.max(10, pct * 300)}px`,
                display: "flex", alignItems: "flex-start", justifyContent: "center", paddingTop: 4,
              }}>
                <span style={{ color: "#fff", fontSize: 9, fontWeight: 700 }}>
                  {(val/1e6).toFixed(1)}mi
                </span>
              </div>
              <div style={{ fontSize: 9, color: cor, fontWeight: 700, marginTop: 4 }}>
                {label}<br/>{(pct*100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── SEM DOCUMENTO — bloco informativo ────────────────────────────────────────
function SemDocumento({ tipo, impacto, solicitar }) {
  return (
    <div style={{
      background: "#fff8ee", border: "1px solid #f59e0b33",
      borderRadius: 10, padding: 16,
    }}>
      <div style={{ fontSize: 12, fontWeight: 700, color: "#b45309", marginBottom: 8 }}>
        ⚠ {tipo} não anexado — análise conservadora aplicada
      </div>
      <div style={{ fontSize: 11, color: TEXT, marginBottom: 8 }}>
        <b>Impacto no score:</b> {impacto}
      </div>
      <div style={{ fontSize: 11, color: MUTED, marginBottom: 6 }}>
        <b>Para análise completa, solicitar:</b>
      </div>
      {solicitar.map((s, i) => (
        <div key={i} style={{ fontSize: 11, color: TEXT, marginBottom: 3,
          paddingLeft: 8, borderLeft: "2px solid #f59e0b66" }}>
          • {s}
        </div>
      ))}
      <div style={{ marginTop: 10, fontSize: 10, color: "#b45309", fontStyle: "italic" }}>
        A ausência de demonstrações financeiras não equivale a saúde financeira.
        O motor P.I.L.D.E.R™ aplica penalidade conservadora automaticamente.
      </div>
    </div>
  );
}

// ── BLOCO BALANÇO ─────────────────────────────────────────────────────────────
function BlocoBalanco({ bal }) {
  const [aberto, setAberto] = useState(true);
  const ind = bal?.indicadores || {};
  const temDados = bal?.disponivel && Object.keys(ind).length > 0;

  const indicadores = [
    { label: "Receita Bruta", valor: fmt(ind.receita_bruta), classif: null, cor: null },
    { label: "Receita Líquida (ROL)", valor: fmt(ind.receita_liquida), classif: null, cor: null },
    { label: "Lucro Bruto", valor: fmt(ind.lucro_bruto),
      classif: ind.margem_bruta ? `Margem ${ind.margem_bruta?.toFixed(1)}%` : null,
      cor: (ind.margem_bruta||0) >= 25 ? "#0e7a5a" : "#b45309" },
    { label: "Lucro Líquido", valor: fmt(ind.lucro_liquido),
      classif: ind.margem_liquida != null ? `${ind.margem_liquida?.toFixed(1)}%` : null,
      cor: (ind.margem_liquida||0) >= 5 ? "#0e7a5a" : (ind.margem_liquida||0) >= 0 ? "#b45309" : "#c0392b" },
    { label: "EBITDA", valor: fmt(ind.ebitda), classif: null, cor: null },
    { label: "Ativo Total", valor: fmt(ind.ativo_total), classif: null, cor: null },
    { label: "Patrimônio Líquido", valor: fmt(ind.patrimonio_liquido),
      classif: ind.pl_sobre_ativo ? `${ind.pl_sobre_ativo?.toFixed(1)}% do ativo` : null,
      cor: (ind.pl_sobre_ativo||0) >= 40 ? "#0e7a5a" : "#b45309" },
    { label: "Caixa e Disponível", valor: fmt(ind.caixa_disponivel), classif: null, cor: null },
    { label: "Estoques", valor: fmt(ind.estoques), classif: null, cor: null },
    { label: "Liquidez Corrente", valor: fmt(ind.liquidez_corrente, "mult"),
      classif: ind.liquidez_corrente >= 1.5 ? "BOM" : ind.liquidez_corrente >= 1.0 ? "ACEITÁVEL" : "ATENÇÃO",
      cor: (ind.liquidez_corrente||0) >= 1.5 ? "#0e7a5a" : (ind.liquidez_corrente||0) >= 1.0 ? "#b45309" : "#c0392b" },
    { label: "Capital de Giro Líq.", valor: fmt(ind.capital_giro_liquido),
      classif: (ind.capital_giro_liquido||0) > 0 ? "SÓLIDO" : "NEGATIVO",
      cor: (ind.capital_giro_liquido||0) > 0 ? "#0e7a5a" : "#c0392b" },
  ].filter(i => i.valor !== "—");

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`,
      borderRadius: 14, overflow: "hidden", marginBottom: 16 }}>
      <div style={{
        background: NAVY, padding: "14px 20px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        cursor: "pointer",
      }} onClick={() => setAberto(a => !a)}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>
            📊 Análise de Balanço / DRE
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
            {temDados
              ? `${bal.arquivo} · ${bal.red_flags?.length||0} alertas · ${bal.green_flags?.length||0} positivos`
              : "Documento não anexado — clique para ver o que solicitar"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {bal && (
            <span style={{
              background: (bal.pontos||0) >= 0 ? "#064e3b" : "#450a0a",
              color: (bal.pontos||0) >= 0 ? "#34d399" : "#f87171",
              borderRadius: 6, padding: "3px 10px",
              fontSize: 12, fontWeight: 700, fontFamily: "monospace",
            }}>{(bal.pontos||0) > 0 ? "+" : ""}{bal.pontos||"-8"} pts</span>
          )}
          <span style={{ color: "#94a3b8" }}>{aberto ? "▲" : "▼"}</span>
        </div>
      </div>

      {aberto && (
        <div style={{ padding: 20 }}>
          {!temDados ? (
            <SemDocumento
              tipo="Balanço / DRE"
              impacto="Penalidade de -8 pts aplicada. Análise financeira não realizada."
              solicitar={[
                "Balanço Patrimonial dos últimos 2 exercícios (2023 e 2024)",
                "DRE — Demonstração do Resultado do Exercício",
                "DFC — Demonstração do Fluxo de Caixa",
                "Preferencialmente auditados por auditor independente",
                "Aceitável: balancete gerencial ou relatório Credinfar/bureau"
              ]}
            />
          ) : (
            <>
              {/* Indicadores */}
              <Secao titulo="Indicadores Extraídos do Documento">
                <div style={{ borderRadius: 8, overflow: "hidden", border: `1px solid ${BORDER}` }}>
                  {indicadores.map((ind, i) => (
                    <Linha key={i} label={ind.label} valor={ind.valor}
                      classif={ind.classif} corClass={ind.cor} />
                  ))}
                </div>
              </Secao>

              {/* Flags */}
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
                <FlagBlock titulo="🔴 Red Flags" items={bal.red_flags} cor="#c0392b" bg="#fff0ee"
                  vazio="Nenhum alerta crítico identificado" />
                <FlagBlock titulo="🟡 Yellow Flags" items={bal.yellow_flags} cor="#b45309" bg="#fff8ee"
                  vazio="Nenhum ponto de atenção" />
                <FlagBlock titulo="🟢 Green Flags" items={bal.green_flags} cor="#0e7a5a" bg="#edfaf5"
                  vazio="Nenhum ponto positivo identificado" />
              </div>

              {/* Parecer */}
              {bal.parecer_gestor && (
                <details style={{ background: BG, border: `1px solid ${BORDER}`,
                  borderRadius: 8, padding: 12 }}>
                  <summary style={{ cursor: "pointer", fontSize: 11, color: GOLD,
                    fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
                    Ver Parecer Completo do Analista
                  </summary>
                  <div style={{
                    marginTop: 10, fontSize: 11, color: TEXT, lineHeight: 1.8,
                    whiteSpace: "pre-wrap", fontFamily: "monospace",
                    maxHeight: 350, overflowY: "auto",
                  }}>
                    {bal.parecer_gestor}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── BLOCO CISP ────────────────────────────────────────────────────────────────
function BlocoCISP({ cisp }) {
  const [aberto, setAberto] = useState(true);
  const ind = cisp?.indicadores || {};
  const debito = ind.debito_atual;
  const temDados = cisp?.disponivel && (debito || Object.keys(ind).length > 0);

  const indicadores = [
    { label: "Classe de Risco", valor: ind.classe_risco || "—",
      classif: ind.classe_risco === "A" || ind.classe_risco === "B" ? "ESTÁVEL" : "ATENÇÃO",
      cor: ind.classe_risco === "A" || ind.classe_risco === "B" ? "#0e7a5a" : "#c0392b" },
    { label: "Débito Atual Total", valor: fmt(debito), classif: null, cor: null },
    { label: "Vencido +5 dias", valor: fmt(ind.vencido_5d),
      classif: debito && ind.vencido_5d ? `${(ind.vencido_5d/debito*100).toFixed(1)}%` : null,
      cor: debito && (ind.vencido_5d/debito) >= 0.4 ? "#c0392b" : "#b45309" },
    { label: "Vencido +15 dias", valor: fmt(ind.vencido_15d),
      classif: debito && ind.vencido_15d ? `${(ind.vencido_15d/debito*100).toFixed(1)}%` : null,
      cor: debito && (ind.vencido_15d/debito) >= 0.3 ? "#c0392b" : "#b45309" },
    { label: "Vencido +30 dias", valor: fmt(ind.vencido_30d),
      classif: debito && ind.vencido_30d ? `${(ind.vencido_30d/debito*100).toFixed(1)}%` : null,
      cor: debito && (ind.vencido_30d/debito) >= 0.25 ? "#c0392b" : "#b45309" },
    { label: "PMV (Prazo Médio)", valor: ind.pmv_dias ? `${ind.pmv_dias} dias` : "—", classif: null, cor: null },
    { label: "Garantia / Seguro", valor: fmt(ind.garantia_valor),
      classif: debito && ind.garantia_valor ? `${(ind.garantia_valor/debito*100).toFixed(0)}% cobertura` : null,
      cor: debito && (ind.garantia_valor/debito) < 0.15 ? "#b45309" : "#0e7a5a" },
    { label: "Assoc. c/ Débito", valor: ind.associadas_debito ? `${ind.associadas_debito} fornecedores` : "—", classif: null, cor: null },
  ].filter(i => i.valor !== "—");

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`,
      borderRadius: 14, overflow: "hidden", marginBottom: 16 }}>
      <div style={{
        background: "#1a2a3a", padding: "14px 20px",
        display: "flex", justifyContent: "space-between", alignItems: "center",
        cursor: "pointer",
      }} onClick={() => setAberto(a => !a)}>
        <div>
          <div style={{ fontSize: 14, fontWeight: 700, color: "#fff" }}>
            📋 Análise CISP / Credinfar — Comportamento Comercial
          </div>
          <div style={{ fontSize: 11, color: "#94a3b8", marginTop: 2 }}>
            {temDados
              ? `${cisp.arquivo} · ${cisp.red_flags?.length||0} alertas · ${cisp.green_flags?.length||0} positivos${debito ? ` · Débito: ${fmt(debito)}` : ""}`
              : "Ficha não anexada — clique para ver o que solicitar"}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          {cisp && (
            <span style={{
              background: (cisp.pontos||0) >= 0 ? "#064e3b" : "#450a0a",
              color: (cisp.pontos||0) >= 0 ? "#34d399" : "#f87171",
              borderRadius: 6, padding: "3px 10px",
              fontSize: 12, fontWeight: 700, fontFamily: "monospace",
            }}>{(cisp.pontos||0) > 0 ? "+" : ""}{cisp.pontos||"0"} pts</span>
          )}
          <span style={{ color: "#94a3b8" }}>{aberto ? "▲" : "▼"}</span>
        </div>
      </div>

      {aberto && (
        <div style={{ padding: 20 }}>
          {!temDados ? (
            <SemDocumento
              tipo="Ficha CISP / Credinfar"
              impacto="Sem penalidade direta, mas comportamento comercial não avaliado — risco subestimado."
              solicitar={[
                "Ficha CISP completa (Credinfar, SPC, Boa Vista ou similar)",
                "Avaliação Analítica — Pessoa Jurídica",
                "Relatório de aging por setor/fornecedor",
                "Histórico de 12 meses de pontualidade comercial",
                "Relatório de garantias e limites concedidos pelo mercado"
              ]}
            />
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 14, marginBottom: 14 }}>
                <Secao titulo="Indicadores da Ficha CISP">
                  <div style={{ borderRadius: 8, overflow: "hidden", border: `1px solid ${BORDER}` }}>
                    {indicadores.map((ind, i) => (
                      <Linha key={i} label={ind.label} valor={ind.valor}
                        classif={ind.classif} corClass={ind.cor} />
                    ))}
                  </div>
                </Secao>
                <Secao titulo="Aging — Exposição por Faixa">
                  <AgingBar indicadores={ind} debito={debito} />
                </Secao>
              </div>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 10, marginBottom: 14 }}>
                <FlagBlock titulo="🔴 Red Flags" items={cisp.red_flags} cor="#c0392b" bg="#fff0ee"
                  vazio="Nenhum alerta crítico" />
                <FlagBlock titulo="🟡 Yellow Flags" items={cisp.yellow_flags} cor="#b45309" bg="#fff8ee"
                  vazio="Nenhum ponto de atenção" />
                <FlagBlock titulo="🟢 Green Flags" items={cisp.green_flags} cor="#0e7a5a" bg="#edfaf5"
                  vazio="Nenhum ponto positivo" />
              </div>

              {cisp.parecer_gestor && (
                <details style={{ background: BG, border: `1px solid ${BORDER}`,
                  borderRadius: 8, padding: 12 }}>
                  <summary style={{ cursor: "pointer", fontSize: 11, color: GOLD,
                    fontWeight: 700, textTransform: "uppercase", letterSpacing: 1 }}>
                    Ver Parecer Completo do Analista
                  </summary>
                  <div style={{
                    marginTop: 10, fontSize: 11, color: TEXT, lineHeight: 1.8,
                    whiteSpace: "pre-wrap", fontFamily: "monospace",
                    maxHeight: 350, overflowY: "auto",
                  }}>
                    {cisp.parecer_gestor}
                  </div>
                </details>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

// ── EXPORT PRINCIPAL ──────────────────────────────────────────────────────────
export default function RelatorioFinanceiro({ resultado }) {
  if (!resultado) return null;

  // SEMPRE renderiza — mesmo sem balanço ou CISP
  const bal = resultado.balanco_detalhado || {
    disponivel: false, pontos: -8,
    red_flags: [], yellow_flags: [], green_flags: [], indicadores: {},
  };
  const cisp = resultado.cisp_detalhado || {
    disponivel: false, pontos: 0,
    red_flags: [], yellow_flags: [], green_flags: [], indicadores: {},
  };

  return (
    <div>
      <BlocoBalanco bal={bal} />
      <BlocoCISP cisp={cisp} />
    </div>
  );
}
