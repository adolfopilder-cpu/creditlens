// src/pages/AnalisePage.js
import { useState } from "react";
import { analisarCNPJ, baixarPDF } from "../hooks/useApi";
import {
  ScoreBadge, RatingBadge, RiscoTag, FlagList, Spinner, KpiCard, ConectorBadge
} from "../components/ui";

function formatCNPJ(v) {
  const d = v.replace(/\D/g, "").slice(0, 14);
  return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/, "$1.$2.$3/$4-$5");
}

export default function AnalisePage() {
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);

  async function handleAnalise(e) {
    e.preventDefault();
    if (!cnpj) return;
    setLoading(true); setErro(""); setResultado(null);
    try {
      const r = await analisarCNPJ(cnpj);
      setResultado(r);
    } catch (err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handlePDF() {
    setPdfLoading(true);
    try { await baixarPDF(cnpj); }
    catch (e) { setErro("Erro ao gerar PDF: " + e.message); }
    finally { setPdfLoading(false); }
  }

  const r = resultado;

  return (
    <div>
      {/* Formulário de busca */}
      <div style={{ background:"#0a1628", border:"1px solid #1e293b",
        borderRadius:14, padding:28, marginBottom:24 }}>
        <div style={{ fontSize:14, fontWeight:700, marginBottom:16, color:"#94a3b8" }}>
          Consulta Pontual de CNPJ
        </div>
        <form onSubmit={handleAnalise} style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
          <input
            value={formatCNPJ(cnpj)}
            onChange={e => setCnpj(e.target.value.replace(/\D/g, ""))}
            placeholder="00.000.000/0000-00"
            maxLength={18}
            style={{ flex:1, minWidth:220, background:"#060d1a", border:"1px solid #1e293b",
              borderRadius:8, padding:"10px 14px", color:"#e2e8f0", fontSize:15,
              fontFamily:"monospace", letterSpacing:1, outline:"none" }}
          />
          <button type="submit" disabled={loading || cnpj.length < 14}
            style={{ background: cnpj.length < 14 ? "#1e293b" : "linear-gradient(135deg,#3b82f6,#6366f1)",
              border:"none", borderRadius:8, padding:"10px 28px", color:"#fff",
              fontWeight:700, fontSize:14, cursor: cnpj.length < 14 ? "not-allowed" : "pointer" }}>
            {loading ? "Analisando..." : "Analisar"}
          </button>
          {r && (
            <button type="button" onClick={handlePDF} disabled={pdfLoading}
              style={{ background:"#0f172a", border:"1px solid #334155", borderRadius:8,
                padding:"10px 20px", color:"#94a3b8", fontSize:13, cursor:"pointer", fontWeight:600 }}>
              {pdfLoading ? "Gerando..." : "⬇ PDF"}
            </button>
          )}
        </form>
        {erro && (
          <div style={{ marginTop:12, padding:12, background:"#450a0a33",
            border:"1px solid #ef444433", borderRadius:8, color:"#f87171", fontSize:13 }}>
            {erro}
          </div>
        )}
      </div>

      {loading && <Spinner />}

      {r && (
        <>
          {/* Header da empresa */}
          <div style={{ background:"#0a1628", border:"1px solid #1e293b",
            borderRadius:14, padding:24, marginBottom:20 }}>
            <div style={{ display:"flex", justifyContent:"space-between",
              alignItems:"flex-start", flexWrap:"wrap", gap:12 }}>
              <div>
                <div style={{ fontSize:20, fontWeight:800, marginBottom:4 }}>{r.empresa || "—"}</div>
                <div style={{ fontSize:12, color:"#475569", fontFamily:"monospace" }}>
                  {formatCNPJ(r.cnpj)} · {r.dados?.receita?.uf} · {r.dados?.receita?.municipio}
                </div>
                <div style={{ fontSize:11, color:"#334155", marginTop:3 }}>
                  {r.dados?.receita?.cnae_principal}
                </div>
              </div>
              <div style={{ display:"flex", gap:10, alignItems:"center", flexWrap:"wrap" }}>
                <ScoreBadge score={r.score} />
                <RatingBadge rating={r.rating} />
                <RiscoTag risco={r.classificacao_risco} />
              </div>
            </div>
          </div>

          {/* KPIs */}
          <div style={{ display:"flex", gap:12, marginBottom:20, flexWrap:"wrap" }}>
            <KpiCard label="PD Estimada" value={`${r.pd}%`}
              color={r.pd > 35 ? "#f87171" : r.pd > 25 ? "#fbbf24" : "#34d399"} />
            <KpiCard label="Prazo Sugerido" value={r.prazo_sugerido} color="#a78bfa"
              sub="dias corridos" />
            <KpiCard label="Sinais RJ" value={r.sinais_rj?.length || 0}
              color={r.sinais_rj?.length > 0 ? "#f97316" : "#34d399"} />
            <KpiCard label="Red Flags" value={r.red_flags?.length || 0}
              color={r.red_flags?.length > 0 ? "#ef4444" : "#34d399"} />
            <KpiCard label="Yellow Flags" value={r.yellow_flags?.length || 0}
              color={r.yellow_flags?.length > 0 ? "#f59e0b" : "#34d399"} />
          </div>

          {/* Flags */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)",
            gap:14, marginBottom:20 }}>
            <FlagList title="🟢 Green Flags" items={r.green_flags} color="#10b981" />
            <FlagList title="🟡 Yellow Flags" items={r.yellow_flags} color="#f59e0b" />
            <FlagList title="🔴 Red Flags" items={r.red_flags} color="#ef4444" />
          </div>

          {/* Sinais RJ */}
          {r.sinais_rj?.length > 0 && (
            <div style={{ background:"#450a0a22", border:"1px solid #ef444433",
              borderRadius:12, padding:18, marginBottom:20 }}>
              <div style={{ fontSize:12, fontWeight:700, color:"#f97316", marginBottom:10 }}>
                ⚠ Sinais de Stress / Recuperação Judicial
              </div>
              {r.sinais_rj.map((s, i) => (
                <div key={i} style={{ fontSize:12, color:"#fca5a5", marginBottom:4 }}>• {s}</div>
              ))}
            </div>
          )}

          {/* Recomendação */}
          <div style={{ background:"#0a1628", border:"1px solid #1e293b",
            borderRadius:14, padding:20, marginBottom:20 }}>
            <div style={{ fontSize:12, fontWeight:700, color:"#64748b",
              letterSpacing:1, textTransform:"uppercase", marginBottom:12 }}>
              Recomendação de Crédito
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
              <div>
                <div style={{ fontSize:10, color:"#475569", marginBottom:4 }}>LIMITE SUGERIDO</div>
                <div style={{ fontSize:13, fontWeight:600, color:"#e2e8f0" }}>{r.limite_sugerido}</div>
              </div>
              <div>
                <div style={{ fontSize:10, color:"#475569", marginBottom:4 }}>MONITORAMENTO</div>
                <div style={{ fontSize:13, fontWeight:600, color:"#e2e8f0" }}>{r.plano_monitoramento}</div>
              </div>
              <div style={{ gridColumn:"1/-1" }}>
                <div style={{ fontSize:10, color:"#475569", marginBottom:6 }}>GARANTIAS RECOMENDADAS</div>
                <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
                  {r.garantias_recomendadas?.map((g, i) => (
                    <span key={i} style={{ background:"#1e293b", borderRadius:6,
                      padding:"4px 10px", fontSize:11, color:"#94a3b8" }}>{g}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* Conectores */}
          <div style={{ background:"#0a1628", border:"1px solid #1e293b",
            borderRadius:14, padding:20, marginBottom:20 }}>
            <div style={{ fontSize:12, fontWeight:700, color:"#64748b",
              letterSpacing:1, textTransform:"uppercase", marginBottom:12 }}>
              Status dos Conectores nesta Análise
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"repeat(3,1fr)", gap:10 }}>
              {r.conectores && Object.entries(r.conectores).map(([key, val]) => (
                <div key={key} style={{ background:"#0f172a", borderRadius:8, padding:12 }}>
                  <div style={{ display:"flex", justifyContent:"space-between",
                    alignItems:"center", marginBottom:6 }}>
                    <span style={{ fontSize:12, fontWeight:600,
                      textTransform:"capitalize", color:"#e2e8f0" }}>{key}</span>
                    <ConectorBadge status={val.status} />
                  </div>
                  <div style={{ fontSize:10, color:"#475569", lineHeight:1.4 }}>{val.summary}</div>
                </div>
              ))}
            </div>
          </div>

          {/* Memória de cálculo */}
          <details style={{ background:"#0a1628", border:"1px solid #1e293b",
            borderRadius:14, padding:16 }}>
            <summary style={{ cursor:"pointer", fontSize:12, color:"#475569",
              fontWeight:700, letterSpacing:1, textTransform:"uppercase" }}>
              Memória de Cálculo
            </summary>
            <div style={{ marginTop:12, display:"flex", gap:10, flexWrap:"wrap" }}>
              {r.memoria_calculo && Object.entries(r.memoria_calculo).map(([k, v]) => (
                <div key={k} style={{ background:"#0f172a", borderRadius:8,
                  padding:"8px 14px", minWidth:100 }}>
                  <div style={{ fontSize:10, color:"#475569", marginBottom:3,
                    textTransform:"capitalize" }}>{k}</div>
                  <div style={{ fontSize:16, fontWeight:700, fontFamily:"monospace",
                    color: typeof v === "number" && v > 0 ? "#34d399" : v < 0 ? "#f87171" : "#94a3b8" }}>
                    {typeof v === "number" ? (v > 0 ? `+${v}` : v) : v}
                  </div>
                </div>
              ))}
            </div>
          </details>
        </>
      )}
    </div>
  );
}
