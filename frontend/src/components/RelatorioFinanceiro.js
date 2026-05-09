// src/components/RelatorioFinanceiro.js
// Exibição de balanço (modelo Disdal) + CISP (modelo Okajima)
import { useState } from "react";

const NAVY = "#1E3A5F";
const GOLD = "#b49303";
const BG = "#f5f0e8";
const CARD = "#ffffff";
const BORDER = "#d4c9a8";
const MUTED = "#6b6b7b";
const TEXT = "#1a1a2e";

function fmt(v, tipo = "moeda") {
  if (v == null) return "N/D";
  if (tipo === "moeda") return `R$ ${Number(v).toLocaleString("pt-BR", { minimumFractionDigits: 0 })}`;
  if (tipo === "pct") return `${Number(v).toFixed(1)}%`;
  if (tipo === "mult") return `${Number(v).toFixed(2)}×`;
  return String(v);
}

function Secao({ titulo, children, cor = NAVY }) {
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{
        fontSize: 12, fontWeight: 800, color: cor,
        letterSpacing: 1.5, textTransform: "uppercase",
        borderBottom: `2px solid ${cor}22`, paddingBottom: 6, marginBottom: 12,
      }}>{titulo}</div>
      {children}
    </div>
  );
}

function TabelaIndicadores({ linhas }) {
  return (
    <div style={{
      background: BG, borderRadius: 8, overflow: "hidden",
      border: `1px solid ${BORDER}`, marginBottom: 12,
    }}>
      {linhas.map(([label, valor, classif, corClass], i) => (
        <div key={i} style={{
          display: "flex", justifyContent: "space-between", alignItems: "center",
          padding: "8px 14px", borderBottom: i < linhas.length-1 ? `1px solid ${BORDER}` : "none",
          background: i % 2 === 0 ? CARD : BG,
        }}>
          <span style={{ fontSize: 12, color: TEXT, fontWeight: 500 }}>{label}</span>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
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
      ))}
    </div>
  );
}

function FlagList({ titulo, items, cor, bg }) {
  if (!items?.length) return null;
  return (
    <div style={{
      background: bg, border: `1px solid ${cor}33`,
      borderRadius: 10, padding: 14, marginBottom: 10,
    }}>
      <div style={{ fontSize: 11, fontWeight: 800, color: cor,
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 8 }}>
        {titulo} ({items.length})
      </div>
      {items.map((f, i) => (
        <div key={i} style={{
          fontSize: 12, color: TEXT, marginBottom: 5,
          paddingLeft: 10, borderLeft: `3px solid ${cor}66`,
          lineHeight: 1.5,
        }}>{f}</div>
      ))}
    </div>
  );
}

function PainelRisco({ indicadores, debito }) {
  if (!indicadores || !debito) return null;
  const items = [];
  if (indicadores.vencido_30d)
    items.push({ label: "Volume vencido maduro (+30d)", score: Math.min(10, (indicadores.vencido_30d / debito) * 40) });
  if (indicadores.vencido_15d)
    items.push({ label: "Sinais de estresse (+15d)", score: Math.min(10, (indicadores.vencido_15d / debito) * 30) });
  if (indicadores.vencido_5d)
    items.push({ label: "Pontualidade comercial", score: Math.min(10, (indicadores.vencido_5d / debito) * 25) });
  if (indicadores.garantia_valor)
    items.push({ label: "Mitigadores / garantias", score: Math.max(0, 5 - (indicadores.garantia_valor / debito) * 10) });

  if (!items.length) return null;
  const sorted = [...items].sort((a, b) => b.score - a.score);

  return (
    <div style={{ background: BG, borderRadius: 10, padding: 16, marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: MUTED,
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Painel Sintético de Risco (0=baixo | 10=alto)
      </div>
      {sorted.map(({ label, score }, i) => {
        const color = score >= 7 ? "#c0392b" : score >= 4 ? "#b45309" : "#0e7a5a";
        return (
          <div key={i} style={{ marginBottom: 8 }}>
            <div style={{ display: "flex", justifyContent: "space-between",
              marginBottom: 3, fontSize: 11, color: TEXT }}>
              <span>{label}</span>
              <span style={{ fontWeight: 700, color, fontFamily: "monospace" }}>
                {score.toFixed(1)}
              </span>
            </div>
            <div style={{ height: 10, background: "#e5e0d5", borderRadius: 5, overflow: "hidden" }}>
              <div style={{
                width: `${score * 10}%`, height: "100%",
                background: color, borderRadius: 5,
                transition: "width 0.8s ease",
              }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}

function AgingBar({ indicadores, debito }) {
  if (!debito) return null;
  const faixas = [
    { label: "Vencido +5d", key: "vencido_5d", pct_key: "pct_vencido_5d" },
    { label: "Vencido +15d", key: "vencido_15d", pct_key: "pct_vencido_15d" },
    { label: "Vencido +30d", key: "vencido_30d", pct_key: "pct_vencido_30d" },
    { label: "Vencido +60d", key: "vencido_60d" },
    { label: "Vencido +90d", key: "vencido_90d" },
  ].filter(f => indicadores[f.key]);

  if (!faixas.length) return null;

  return (
    <div style={{ background: BG, borderRadius: 10, padding: 16, marginBottom: 12 }}>
      <div style={{ fontSize: 11, fontWeight: 700, color: MUTED,
        textTransform: "uppercase", letterSpacing: 1, marginBottom: 12 }}>
        Exposição e Aging (R$ mi)
      </div>
      <div style={{
        display: "grid",
        gridTemplateColumns: `repeat(${faixas.length + 1}, 1fr)`,
        gap: 8, marginBottom: 8,
      }}>
        {/* Débito total */}
        <div style={{ textAlign: "center" }}>
          <div style={{
            background: "#1E3A5F", borderRadius: 6,
            height: 120, display: "flex", alignItems: "flex-end",
            justifyContent: "center", paddingBottom: 8, position: "relative",
          }}>
            <span style={{ color: "#fff", fontSize: 11, fontWeight: 700 }}>
              {(debito / 1e6).toFixed(1)}
            </span>
          </div>
          <div style={{ fontSize: 10, color: MUTED, marginTop: 4 }}>Débito atual</div>
        </div>
        {faixas.map(({ label, key, pct_key }) => {
          const val = indicadores[key];
          const pct = val / debito;
          const color = pct >= 0.3 ? "#c0392b" : pct >= 0.15 ? "#b45309" : "#1E3A5F";
          return (
            <div key={key} style={{ textAlign: "center" }}>
              <div style={{
                background: color, borderRadius: 6,
                height: `${Math.max(20, pct * 400)}px`,
                display: "flex", alignItems: "flex-end",
                justifyContent: "center", paddingBottom: 6,
              }}>
                <span style={{ color: "#fff", fontSize: 10, fontWeight: 700 }}>
                  {(val / 1e6).toFixed(1)}
                </span>
              </div>
              <div style={{ fontSize: 10, color: MUTED, marginTop: 4 }}>{label}</div>
              <div style={{ fontSize: 10, color, fontWeight: 700 }}>
                {(pct * 100).toFixed(1)}%
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── BLOCO BALANÇO ─────────────────────────────────────────────────────────────
function BlocoBalanco({ bal }) {
  const [aberto, setAberto] = useState(true);
  if (!bal) return null;

  const ind = bal.indicadores || {};

  const dre = [
    ["Receita Bruta", fmt(ind.receita_bruta), null, null],
    ["Receita Líquida (ROL)", fmt(ind.receita_liquida), null, null],
    ["Lucro Bruto", fmt(ind.lucro_bruto), ind.margem_bruta ? `Margem ${ind.margem_bruta?.toFixed(1)}%` : null, "#0e7a5a"],
    ["Lucro Líquido", fmt(ind.lucro_liquido), ind.margem_liquida ? `${ind.margem_liquida?.toFixed(1)}%` : null,
      ind.margem_liquida > 0 ? "#0e7a5a" : "#c0392b"],
    ["EBITDA", fmt(ind.ebitda), null, null],
    ["Resultado Financeiro Líq.", fmt(ind.resultado_financeiro),
      ind.resultado_financeiro > 0 ? "POSITIVO" : "NEGATIVO",
      ind.resultado_financeiro > 0 ? "#0e7a5a" : "#c0392b"],
  ].filter(([_, v]) => v !== "R$ 0" && v !== "N/D");

  const bp = [
    ["Ativo Total", fmt(ind.ativo_total), null, null],
    ["Caixa e Disponível", fmt(ind.caixa_disponivel), null, null],
    ["Títulos a Receber", fmt(ind.titulos_receber), null, null],
    ["Estoques", fmt(ind.estoques), null, null],
    ["Patrimônio Líquido", fmt(ind.patrimonio_liquido),
      ind.pl_sobre_ativo ? `${ind.pl_sobre_ativo?.toFixed(1)}% do ativo` : null,
      ind.pl_sobre_ativo >= 40 ? "#0e7a5a" : "#b45309"],
    ["Capital Social", fmt(ind.capital_social), null, null],
    ["Reservas de Lucros", fmt(ind.reservas_lucros), null, null],
  ].filter(([_, v]) => v !== "R$ 0" && v !== "N/D");

  const indicadores_calc = [
    ["Liquidez Corrente", fmt(ind.liquidez_corrente, "mult"),
      ind.liquidez_corrente >= 1.5 ? "BOM" : ind.liquidez_corrente >= 1.0 ? "ACEITÁVEL" : "ATENÇÃO",
      ind.liquidez_corrente >= 1.5 ? "#0e7a5a" : ind.liquidez_corrente >= 1.0 ? "#b45309" : "#c0392b"],
    ["Liquidez Imediata", fmt(ind.liquidez_imediata, "mult"),
      ind.liquidez_imediata < 0.05 ? "BAIXO" : "OK",
      ind.liquidez_imediata < 0.05 ? "#b45309" : "#0e7a5a"],
    ["PL / Ativo Total", fmt(ind.pl_sobre_ativo, "pct"),
      ind.pl_sobre_ativo >= 40 ? "EXCELENTE" : ind.pl_sobre_ativo >= 25 ? "BOM" : "ATENÇÃO",
      ind.pl_sobre_ativo >= 40 ? "#0e7a5a" : ind.pl_sobre_ativo >= 25 ? "#b45309" : "#c0392b"],
    ["Margem Bruta", fmt(ind.margem_bruta, "pct"),
      ind.margem_bruta >= 25 ? "BOA" : ind.margem_bruta >= 15 ? "MODERADA" : "COMPRIMIDA",
      ind.margem_bruta >= 25 ? "#0e7a5a" : ind.margem_bruta >= 15 ? "#b45309" : "#c0392b"],
    ["Margem Líquida", fmt(ind.margem_liquida, "pct"),
      ind.margem_liquida >= 5 ? "SAUDÁVEL" : ind.margem_liquida >= 2 ? "APERTADA" : "CRÍTICA",
      ind.margem_liquida >= 5 ? "#0e7a5a" : ind.margem_liquida >= 2 ? "#b45309" : "#c0392b"],
    ["Capital de Giro Líq.", fmt(ind.capital_giro_liquido),
      ind.capital_giro_liquido > 0 ? "SÓLIDO" : "NEGATIVO",
      ind.capital_giro_liquido > 0 ? "#0e7a5a" : "#c0392b"],
    ["Dívida Fin. / PL", fmt(ind.divida_fin_sobre_pl, "mult"),
      ind.divida_fin_sobre_pl < 0.1 ? "MÍNIMA" : ind.divida_fin_sobre_pl < 0.5 ? "OK" : "ALTA",
      ind.divida_fin_sobre_pl < 0.1 ? "#0e7a5a" : ind.divida_fin_sobre_pl < 0.5 ? "#b45309" : "#c0392b"],
  ].filter(([_, v]) => v !== "N/D");

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
            {bal.arquivo} · {bal.red_flags?.length || 0} red · {bal.yellow_flags?.length || 0} yellow · {bal.green_flags?.length || 0} green
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{
            background: bal.pontos > 0 ? "#064e3b" : "#450a0a",
            color: bal.pontos > 0 ? "#34d399" : "#f87171",
            borderRadius: 6, padding: "3px 10px",
            fontSize: 12, fontWeight: 700, fontFamily: "monospace",
          }}>{bal.pontos > 0 ? "+" : ""}{bal.pontos} pts</span>
          <span style={{ color: "#94a3b8" }}>{aberto ? "▲" : "▼"}</span>
        </div>
      </div>

      {aberto && (
        <div style={{ padding: 20 }}>
          {!bal.disponivel ? (
            <div style={{ background: "#fff8ee", border: "1px solid #f59e0b33",
              borderRadius: 8, padding: 14, color: "#b45309", fontSize: 13 }}>
              ⚠ {bal.resumo}
            </div>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                {dre.length > 0 && (
                  <div>
                    <Secao titulo="DRE — Demonstração do Resultado">
                      <TabelaIndicadores linhas={dre} />
                    </Secao>
                  </div>
                )}
                {bp.length > 0 && (
                  <div>
                    <Secao titulo="Balanço Patrimonial">
                      <TabelaIndicadores linhas={bp} />
                    </Secao>
                  </div>
                )}
              </div>

              {indicadores_calc.length > 0 && (
                <Secao titulo="Indicadores-Chave">
                  <TabelaIndicadores linhas={indicadores_calc} />
                </Secao>
              )}

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
                <FlagList titulo="🔴 Red Flags" items={bal.red_flags} cor="#c0392b" bg="#fff0ee" />
                <FlagList titulo="🟡 Yellow Flags" items={bal.yellow_flags} cor="#b45309" bg="#fff8ee" />
                <FlagList titulo="🟢 Green Flags" items={bal.green_flags} cor="#0e7a5a" bg="#edfaf5" />
              </div>

              {bal.parecer_gestor && (
                <details>
                  <summary style={{ cursor: "pointer", fontSize: 12, color: GOLD,
                    fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
                    marginBottom: 8 }}>
                    Ver Parecer Completo do Analista
                  </summary>
                  <div style={{
                    background: BG, border: `1px solid ${BORDER}`, borderRadius: 8,
                    padding: 14, fontSize: 11, color: TEXT, lineHeight: 1.8,
                    whiteSpace: "pre-wrap", fontFamily: "monospace",
                    maxHeight: 400, overflowY: "auto", marginTop: 8,
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
  if (!cisp) return null;

  const ind = cisp.indicadores || {};
  const debito = ind.debito_atual;

  const indicadores_cisp = [
    ["Classe de Risco", ind.classe_risco || "N/D",
      ind.classe_risco === "A" || ind.classe_risco === "B" ? "ESTÁVEL" : "ATENÇÃO",
      ind.classe_risco === "A" || ind.classe_risco === "B" ? "#0e7a5a" : "#c0392b"],
    ["Débito Atual Total", fmt(debito), null, null],
    ["Vencido +5 dias", fmt(ind.vencido_5d),
      debito && ind.vencido_5d ? `${(ind.vencido_5d/debito*100).toFixed(1)}%` : null,
      debito && ind.vencido_5d/debito >= 0.4 ? "#c0392b" : "#b45309"],
    ["Vencido +15 dias", fmt(ind.vencido_15d),
      debito && ind.vencido_15d ? `${(ind.vencido_15d/debito*100).toFixed(1)}%` : null,
      debito && ind.vencido_15d/debito >= 0.3 ? "#c0392b" : "#b45309"],
    ["Vencido +30 dias", fmt(ind.vencido_30d),
      debito && ind.vencido_30d ? `${(ind.vencido_30d/debito*100).toFixed(1)}%` : null,
      debito && ind.vencido_30d/debito >= 0.25 ? "#c0392b" : "#b45309"],
    ["PMV (Prazo Médio)", ind.pmv_dias ? `${ind.pmv_dias} dias` : "N/D", null, null],
    ["Garantia / Seguro", fmt(ind.garantia_valor), null, "#0e7a5a"],
    ["Associadas c/ Débito", ind.associadas_debito ? `${ind.associadas_debito} empresas` : "N/D", null, null],
    ["Vendas Recentes", ind.vendas_recentes ? `${ind.vendas_recentes} transações` : "N/D", null, null],
    ["Meses de Estabilidade", ind.meses_estabilidade ? `${ind.meses_estabilidade} meses` : "N/D", null, null],
  ].filter(([_, v]) => v !== "N/D" && v !== "R$ 0");

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
            {cisp.arquivo} · {cisp.red_flags?.length || 0} red · {cisp.yellow_flags?.length || 0} yellow · {cisp.green_flags?.length || 0} green
            {debito ? ` · Débito: ${fmt(debito)}` : ""}
          </div>
        </div>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <span style={{
            background: cisp.pontos >= 0 ? "#064e3b" : "#450a0a",
            color: cisp.pontos >= 0 ? "#34d399" : "#f87171",
            borderRadius: 6, padding: "3px 10px",
            fontSize: 12, fontWeight: 700, fontFamily: "monospace",
          }}>{cisp.pontos > 0 ? "+" : ""}{cisp.pontos} pts</span>
          <span style={{ color: "#94a3b8" }}>{aberto ? "▲" : "▼"}</span>
        </div>
      </div>

      {aberto && (
        <div style={{ padding: 20 }}>
          {!cisp.disponivel ? (
            <div style={{ background: "#fff8ee", border: "1px solid #f59e0b33",
              borderRadius: 8, padding: 14, color: "#b45309", fontSize: 13 }}>
              ⚠ Ficha CISP não disponível — análise comportamental não realizada.
            </div>
          ) : (
            <>
              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16, marginBottom: 16 }}>
                <div>
                  <Secao titulo="Indicadores da Ficha">
                    <TabelaIndicadores linhas={indicadores_cisp} />
                  </Secao>
                </div>
                <div>
                  <Secao titulo="Aging e Exposição">
                    <AgingBar indicadores={ind} debito={debito} />
                  </Secao>
                </div>
              </div>

              <Secao titulo="Painel Sintético de Risco">
                <PainelRisco indicadores={ind} debito={debito} />
              </Secao>

              <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 12, marginBottom: 16 }}>
                <FlagList titulo="🔴 Red Flags" items={cisp.red_flags} cor="#c0392b" bg="#fff0ee" />
                <FlagList titulo="🟡 Yellow Flags" items={cisp.yellow_flags} cor="#b45309" bg="#fff8ee" />
                <FlagList titulo="🟢 Green Flags" items={cisp.green_flags} cor="#0e7a5a" bg="#edfaf5" />
              </div>

              {cisp.parecer_gestor && (
                <details>
                  <summary style={{ cursor: "pointer", fontSize: 12, color: GOLD,
                    fontWeight: 700, letterSpacing: 1, textTransform: "uppercase",
                    marginBottom: 8 }}>
                    Ver Parecer Completo do Analista
                  </summary>
                  <div style={{
                    background: BG, border: `1px solid ${BORDER}`, borderRadius: 8,
                    padding: 14, fontSize: 11, color: TEXT, lineHeight: 1.8,
                    whiteSpace: "pre-wrap", fontFamily: "monospace",
                    maxHeight: 400, overflowY: "auto", marginTop: 8,
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
  const bal = resultado.balanco_detalhado;
  const cisp = resultado.cisp_detalhado;
  if (!bal && !cisp) return null;

  return (
    <div>
      <BlocoBalanco bal={bal} />
      <BlocoCISP cisp={cisp} />
    </div>
  );
}
