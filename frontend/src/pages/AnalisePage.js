// src/pages/AnalisePage.js — P.I.L.D.E.R™ v4.0 DEFINITIVO
import { useState } from "react";
import RelatorioFinanceiro from "../components/RelatorioFinanceiro";

const API = process.env.REACT_APP_API_URL || "";
const ASSINATURA = "P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito";

const BG = "#f5f0e8";
const CARD = "#ffffff";
const BORDER = "#d4c9a8";
const NAVY = "#1E3A5F";
const GOLD = "#b49303";
const MUTED = "#6b6b7b";
const TEXT = "#1a1a2e";

const STATUS_COLOR = {
  confirmacao:"#0e7a5a", evidencia:"#16a34a", ausencia:"#0e7a5a",
  indicio:"#b45309", pendente:"#6b6b7b", nao_consultado:"#9ca3af", erro:"#c0392b",
};
const STATUS_LABEL = {
  confirmacao:"✓ Confirmado", evidencia:"✓ Evidência", ausencia:"○ Sem ocorrência",
  indicio:"⚡ Indício", pendente:"⏳ Pendente", nao_consultado:"— Não consultado", erro:"✗ Erro",
};
const RATING_COLOR = {
  AAA:"#0e7a5a",AA:"#16a34a",A:"#15803d",BBB:"#b45309",BB:"#d97706",B:"#ea580c",C:"#c0392b",D:"#7f1d1d"
};
const RISCO_COLOR = { baixo:"#0e7a5a", medio:"#b45309", alto:"#c0392b" };

function fmtCNPJ(cnpj) {
  const d = (cnpj||"").replace(/\D/g,"").slice(0,14);
  return d.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/,"$1.$2.$3/$4-$5");
}

function Badge({ label, color }) {
  return (
    <span style={{ background:`${color}18`, color, border:`1px solid ${color}44`,
      borderRadius:6, padding:"3px 12px", fontWeight:700, fontSize:12,
      fontFamily:"monospace", letterSpacing:1 }}>{label}</span>
  );
}

function ScoreGauge({ score }) {
  const color = score>=75?"#0e7a5a":score>=50?"#b45309":"#c0392b";
  const deg = score*3.6;
  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:6 }}>
      <svg width="110" height="110" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="50" fill="none" stroke="#e5e0d5" strokeWidth="10"/>
        <circle cx="60" cy="60" r="50" fill="none" stroke={color} strokeWidth="10"
          strokeDasharray={`${(deg/360)*314.16} 314.16`}
          strokeDashoffset="78.54" strokeLinecap="round"/>
        <text x="60" y="55" textAnchor="middle" fill={color}
          fontSize="28" fontWeight="800" fontFamily="monospace">{score}</text>
        <text x="60" y="74" textAnchor="middle" fill={MUTED}
          fontSize="11" fontFamily="monospace">/ 100</text>
      </svg>
    </div>
  );
}

function FonteRow({ fonte, idx }) {
  const [open, setOpen] = useState(false);
  const color = STATUS_COLOR[fonte.status] || MUTED;
  const pts = fonte.pontos || 0;
  return (
    <div style={{ borderBottom:`1px solid ${BORDER}` }}>
      <div onClick={()=>setOpen(o=>!o)} style={{
        display:"flex", alignItems:"center", gap:10,
        padding:"10px 16px", cursor:"pointer",
        background: open ? BG : CARD, transition:"background 0.15s" }}>
        <span style={{ fontSize:11, color:MUTED, fontFamily:"monospace", minWidth:24 }}>{idx+1}</span>
        <span style={{ flex:1, fontSize:12, fontWeight:600, color:TEXT }}>{fonte.fonte}
          {fonte.resumo && (
            <span style={{ fontSize:11, color:MUTED, display:"block", marginTop:1, fontWeight:400 }}>
              {fonte.resumo?.slice(0,100)}
            </span>
          )}
        </span>
        <span style={{ fontSize:10, background:`${color}18`, color,
          border:`1px solid ${color}33`, borderRadius:20,
          padding:"2px 8px", fontWeight:700, whiteSpace:"nowrap" }}>
          {STATUS_LABEL[fonte.status]||fonte.status}
        </span>
        <span style={{ fontSize:12, fontFamily:"monospace", fontWeight:700,
          minWidth:40, textAlign:"right",
          color:pts>0?"#0e7a5a":pts<0?"#c0392b":MUTED }}>
          {pts>0?"+":""}{pts}
        </span>
        <span style={{ color:MUTED, fontSize:12 }}>{open?"▲":"▼"}</span>
      </div>
      {open && (
        <div style={{ padding:"10px 16px 14px 50px", background:BG,
          borderLeft:`3px solid ${color}` }}>
          <div style={{ fontSize:12, color:TEXT, marginBottom:6, lineHeight:1.6 }}>
            <b>Resumo:</b> {fonte.resumo}
          </div>
          {fonte.detalhe && (
            <div style={{ fontSize:11, color:MUTED, marginBottom:6, lineHeight:1.5,
              background:CARD, borderRadius:6, padding:"8px 12px",
              border:`1px solid ${BORDER}` }}>
              {fonte.detalhe}
            </div>
          )}
          <div style={{ fontSize:10, color:MUTED, fontFamily:"monospace" }}>
            Consultado em: {fonte.consultado_em} | Pontuação: {pts>0?"+":""}{pts}
          </div>
        </div>
      )}
    </div>
  );
}

async function baixarPDFdoResultado(resultado, balanco, cisp, cnpj, cnd, crf) {
  // Reenvia ao backend e recebe o PDF como blob diretamente
  const form = new FormData();
  form.append("cnpj", cnpj);
  if (balanco) form.append("balanco", balanco);
  if (cisp) form.append("cisp", cisp);

  const res = await fetch(`${API}/api/pdf-download`, {
    method: "POST",
    body: form,
  });

  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }

  // Recebe como blob PDF diretamente
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `PILDER_${cnpj}.pdf`;
  document.body.appendChild(a);
  a.click();
  setTimeout(() => { document.body.removeChild(a); URL.revokeObjectURL(url); }, 200);
}

export default function AnalisePage() {
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [resultado, setResultado] = useState(null);
  const [erro, setErro] = useState("");
  const [pdfLoading, setPdfLoading] = useState(false);
  const [pdfErro, setPdfErro] = useState("");
  const [balanco, setBalanco] = useState(null);
  const [cisp, setCisp] = useState(null);
  const [cnd, setCnd] = useState(null);
  const [crf, setCrf] = useState(null);
  const [filtroFonte, setFiltroFonte] = useState("todas");
  const [buscaFonte, setBuscaFonte] = useState("");

  async function handleAnalise(e) {
    e.preventDefault();
    if (!cnpj) return;
    setLoading(true); setErro(""); setResultado(null);

    try {
      // SEMPRE usa analisar-com-anexo para processar PDFs quando existirem
      // e analisar-completo para análise detalhada
      const form = new FormData();
      form.append("cnpj", cnpj);
      if (balanco) form.append("balanco", balanco);
      if (cisp) form.append("cisp", cisp);
      if (cnd) form.append("cnd", cnd);
      if (crf) form.append("crf", crf);

      // Tenta endpoint completo primeiro
      let res = await fetch(`${API}/api/analisar-completo`, {
        method: "POST",
        body: form,
      });

      // Fallback para analisar-com-anexo
      if (!res.ok) {
        const form2 = new FormData();
        form2.append("cnpj", cnpj);
        if (balanco) form2.append("balanco", balanco);
        if (cisp) form2.append("cisp", cisp);
        res = await fetch(`${API}/api/analisar-com-anexo`, {
          method: "POST",
          body: form2,
        });
      }

      if (!res.ok) {
        const err = await res.json().catch(()=>({}));
        throw new Error(err.detail || `Erro HTTP ${res.status}`);
      }

      const data = await res.json();
      setResultado(data);
    } catch(err) {
      setErro(err.message);
    } finally {
      setLoading(false);
    }
  }

  async function handlePDF() {
    setPdfLoading(true);
    setPdfErro("");
    try {
      await baixarPDFdoResultado(resultado, balanco, cisp, cnpj);
    } catch(e) {
      setPdfErro(e.message);
    } finally {
      setPdfLoading(false);
    }
  }

  const r = resultado;
  const fontesFiltradas = r?.fontes?.filter(f => {
    const matchFiltro = filtroFonte==="todas" || f.status===filtroFonte;
    const matchBusca = !buscaFonte || f.fonte.toLowerCase().includes(buscaFonte.toLowerCase());
    return matchFiltro && matchBusca;
  }) || [];

  return (
    <div>
      {/* ── FORMULÁRIO ── */}
      <div style={{ background:CARD, border:`1px solid ${BORDER}`,
        borderRadius:14, padding:24, marginBottom:20,
        boxShadow:"0 2px 12px #00000011" }}>
        <div style={{ fontSize:11, color:GOLD, fontWeight:700,
          letterSpacing:1.2, textTransform:"uppercase", marginBottom:4 }}>{ASSINATURA}</div>
        <div style={{ fontSize:17, fontWeight:800, marginBottom:16, color:NAVY }}>
          Consulta e Análise de CNPJ
        </div>

        <form onSubmit={handleAnalise} style={{ display:"flex", flexDirection:"column", gap:14 }}>
          <div style={{ display:"flex", gap:12, flexWrap:"wrap" }}>
            <input
              value={fmtCNPJ(cnpj)}
              onChange={e=>setCnpj(e.target.value.replace(/\D/g,""))}
              placeholder="Digite o CNPJ: 00.000.000/0000-00"
              maxLength={18}
              style={{ flex:1, minWidth:240, background:BG, border:`2px solid ${BORDER}`,
                borderRadius:8, padding:"12px 16px", color:TEXT, fontSize:16,
                fontFamily:"monospace", letterSpacing:1, outline:"none" }}
              onFocus={e=>e.target.style.borderColor=GOLD}
              onBlur={e=>e.target.style.borderColor=BORDER}
            />
            <button type="submit" disabled={loading||cnpj.length<14} style={{
              background: cnpj.length<14 ? BORDER : NAVY,
              border:"none", borderRadius:8, padding:"12px 32px",
              color: cnpj.length<14 ? MUTED : "#fff",
              fontWeight:700, fontSize:14,
              cursor:cnpj.length<14?"not-allowed":"pointer" }}>
              {loading ? "⏳ Analisando..." : "🔍 Analisar"}
            </button>
            {r && (
              <button type="button" onClick={handlePDF} disabled={pdfLoading} style={{
                background: pdfLoading ? BORDER : BG,
                border:`1px solid ${BORDER}`, borderRadius:8,
                padding:"12px 20px", color:NAVY, fontSize:13,
                cursor: pdfLoading ? "wait" : "pointer", fontWeight:600 }}>
                {pdfLoading ? "⏳ Gerando PDF..." : "⬇ PDF"}
              </button>
            )}
            {pdfErro && (
              <div style={{ fontSize:11, color:"#c0392b", alignSelf:"center",
                maxWidth:200, lineHeight:1.3 }}>
                ⚠ {pdfErro}
              </div>
            )}
          </div>

          {/* Anexos */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:12 }}>
            <div>
              <div style={{ fontSize:11, color:MUTED, fontWeight:600,
                textTransform:"uppercase", letterSpacing:1, marginBottom:6 }}>
                📊 Balanço / DRE (opcional)
              </div>
              <label style={{ display:"block", background:BG,
                border:`2px dashed ${balanco?GOLD:BORDER}`,
                borderRadius:8, padding:"10px 14px", cursor:"pointer",
                fontSize:13, color:balanco?GOLD:MUTED }}>
                <input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls"
                  onChange={e=>setBalanco(e.target.files?.[0]||null)}
                  style={{ display:"none" }} />
                {balanco ? `✓ ${balanco.name}` : "Clique para anexar Balanço ou DRE"}
              </label>
            </div>
            <div>
              <div style={{ fontSize:11, color:MUTED, fontWeight:600,
                textTransform:"uppercase", letterSpacing:1, marginBottom:6 }}>
                📋 Ficha CISP / Credinfar (opcional)
              </div>
              <label style={{ display:"block", background:BG,
                border:`2px dashed ${cisp?GOLD:BORDER}`,
                borderRadius:8, padding:"10px 14px", cursor:"pointer",
                fontSize:13, color:cisp?GOLD:MUTED }}>
                <input type="file" accept=".pdf,.txt,.csv,.xlsx,.xls"
                  onChange={e=>setCisp(e.target.files?.[0]||null)}
                  style={{ display:"none" }} />
                {cisp ? `✓ ${cisp.name}` : "Clique para anexar Ficha CISP / Credinfar"}
              </label>
            </div>
            <div>
              <div style={{ fontSize:11, color:MUTED, fontWeight:600,
                textTransform:"uppercase", letterSpacing:1, marginBottom:6 }}>
                📄 CND — Certidão Receita/PGFN (opcional)
              </div>
              <label style={{ display:"block", background:BG,
                border:`2px dashed ${cnd?GOLD:BORDER}`,
                borderRadius:8, padding:"10px 14px", cursor:"pointer",
                fontSize:13, color:cnd?GOLD:MUTED }}>
                <input type="file" accept=".pdf"
                  onChange={e=>setCnd(e.target.files?.[0]||null)}
                  style={{ display:"none" }} />
                {cnd ? `✓ ${cnd.name}` : "Clique para anexar CND Receita/PGFN"}
              </label>
            </div>
            <div>
              <div style={{ fontSize:11, color:MUTED, fontWeight:600,
                textTransform:"uppercase", letterSpacing:1, marginBottom:6 }}>
                📄 CRF/FGTS — Caixa Econômica (opcional)
              </div>
              <label style={{ display:"block", background:BG,
                border:`2px dashed ${crf?GOLD:BORDER}`,
                borderRadius:8, padding:"10px 14px", cursor:"pointer",
                fontSize:13, color:crf?GOLD:MUTED }}>
                <input type="file" accept=".pdf"
                  onChange={e=>setCrf(e.target.files?.[0]||null)}
                  style={{ display:"none" }} />
                {crf ? `✓ ${crf.name}` : "Clique para anexar CRF/FGTS"}
              </label>
            </div>
          </div>

          {/* Indicador de arquivos carregados */}
          {(balanco || cisp || cnd || crf) && (
            <div style={{ background:"#edfaf5", border:"1px solid #a7f3d0",
              borderRadius:8, padding:"8px 14px", fontSize:12, color:"#0e7a5a" }}>
              ✓ {[
                balanco && `Balanço: ${balanco.name}`,
                cisp && `CISP: ${cisp.name}`,
                cnd && `CND: ${cnd.name}`,
                crf && `CRF: ${crf.name}`,
              ].filter(Boolean).join(" | ")} — serão analisados e incluídos no relatório
            </div>
          )}
        </form>

        {erro && (
          <div style={{ marginTop:12, padding:12, background:"#fff0ee",
            border:"1px solid #f5c6c6", borderRadius:8, color:"#c0392b", fontSize:13 }}>
            {erro}
          </div>
        )}
      </div>

      {/* Loading */}
      {loading && (
        <div style={{ textAlign:"center", padding:"40px 0", color:MUTED }}>
          <div style={{ fontSize:14, marginBottom:12, fontWeight:600 }}>
            Consultando fontes e analisando documentos...
          </div>
          <div style={{ width:40, height:40, border:`3px solid ${BORDER}`,
            borderTop:`3px solid ${NAVY}`, borderRadius:"50%",
            animation:"spin 0.8s linear infinite", margin:"0 auto" }}/>
          <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
        </div>
      )}

      {r && (
        <>
          {/* ── HEADER EMPRESA ── */}
          <div style={{ background:CARD, border:`1px solid ${BORDER}`,
            borderRadius:14, padding:24, marginBottom:14,
            boxShadow:"0 2px 12px #00000011" }}>
            <div style={{ fontSize:10, color:GOLD, fontWeight:700,
              letterSpacing:1, marginBottom:8 }}>{ASSINATURA}</div>
            <div style={{ display:"flex", justifyContent:"space-between",
              alignItems:"flex-start", flexWrap:"wrap", gap:16 }}>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:22, fontWeight:800, color:NAVY, marginBottom:4 }}>
                  {r.empresa||"—"}
                </div>
                <div style={{ fontSize:12, color:MUTED, fontFamily:"monospace", marginBottom:3 }}>
                  {fmtCNPJ(r.cnpj||"")}
                </div>
                <div style={{ fontSize:11, color:MUTED, marginTop:4 }}>
                  {r.fontes_consultadas} de {r.total_fontes} fontes consultadas
                  {r.fontes_pendentes ? ` · ${r.fontes_pendentes} pendentes` : ""}
                  {r.balanco_detalhado?.disponivel ? " · 📊 Balanço analisado" : ""}
                  {r.cisp_detalhado?.disponivel ? " · 📋 CISP analisada" : ""}
                </div>

                {/* ── Sócios e Grupo Econômico ── */}
                {r.grupo_economico && (
                  <div style={{ marginTop:10, padding:"10px 12px",
                    background:"#f0f4ff", borderRadius:8,
                    border:"1px solid #c7d2fe", fontSize:11 }}>

                    {/* Sócios */}
                    {r.socios_360?.socios && Object.keys(r.socios_360.socios).length > 0 && (
                      <div style={{ marginBottom:8 }}>
                        <div style={{ fontWeight:700, color:NAVY, marginBottom:4, fontSize:11 }}>
                          👥 QUADRO SOCIETÁRIO
                        </div>
                        {Object.entries(r.socios_360.socios).map(([nome, info]) => (
                          <div key={nome} style={{ display:"flex", justifyContent:"space-between",
                            padding:"3px 0", borderBottom:"1px solid #e0e7ff", gap:8 }}>
                            <span style={{ fontWeight:600, color:"#1e3a5f" }}>{nome}</span>
                            <span style={{ color:MUTED }}>{info.qualificacao}</span>
                            {info.alertas?.length > 0 && (
                              <span style={{ color:"#c0392b", fontWeight:700 }}>⚠ ALERTA</span>
                            )}
                          </div>
                        ))}
                      </div>
                    )}

                    {/* Grupo Econômico */}
                    {r.grupo_economico?.total > 1 && (
                      <div>
                        <div style={{ fontWeight:700, color:NAVY, marginBottom:4, fontSize:11 }}>
                          🏢 GRUPO ECONÔMICO — {r.grupo_economico.total} estabelecimentos
                        </div>
                        {r.grupo_economico.filiais?.map(f => (
                          <div key={f.cnpj} style={{ display:"flex", gap:8,
                            padding:"3px 0", borderBottom:"1px solid #e0e7ff",
                            fontSize:10, color:MUTED }}>
                            <span style={{ fontFamily:"monospace", color:NAVY }}>
                              {f.cnpj?.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{2})/,"$1.$2.$3/$4-$5")}
                            </span>
                            <span>{f.municipio}/{f.uf}</span>
                            <span style={{ color:f.situacao==="ATIVA"?"#0e7a5a":"#c0392b",
                              fontWeight:700 }}>{f.situacao}</span>
                          </div>
                        ))}
                        {r.grupo_economico?.alerta_grupo && (
                          <div style={{ marginTop:4, color:"#b45309", fontWeight:700 }}>
                            ⚠ Cross-default: {Object.keys(r.grupo_economico.cross_default||{}).length} sócio(s) em múltiplos CNPJs
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}
              </div>
              <div style={{ display:"flex", flexDirection:"column", alignItems:"center", gap:10 }}>
                <ScoreGauge score={r.score} />
                <div style={{ display:"flex", gap:8, flexWrap:"wrap", justifyContent:"center" }}>
                  <Badge label={r.rating} color={RATING_COLOR[r.rating]||MUTED} />
                  <Badge label={(r.classificacao_risco||"").toUpperCase()}
                    color={RISCO_COLOR[r.classificacao_risco]||MUTED} />
                  <Badge label={`PD ${r.pd}%`}
                    color={r.pd>35?"#c0392b":r.pd>25?"#b45309":"#0e7a5a"} />
                </div>
              </div>
            </div>
          </div>

          {/* ── KPIs ── */}
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)",
            gap:10, marginBottom:14 }}>
            {[
              {l:"Score",v:r.score,c:r.score>=75?"#0e7a5a":r.score>=50?"#b45309":"#c0392b"},
              {l:"Rating",v:r.rating,c:RATING_COLOR[r.rating]},
              {l:"PD Estimada",v:`${r.pd}%`,c:r.pd>35?"#c0392b":r.pd>25?"#b45309":"#0e7a5a"},
              {l:"Fontes OK",v:`${r.fontes_consultadas}/${r.total_fontes}`,c:NAVY},
            ].map(({l,v,c})=>(
              <div key={l} style={{ background:CARD, border:`1px solid ${BORDER}`,
                borderRadius:10, padding:"14px 16px",
                boxShadow:"0 1px 6px #00000008" }}>
                <div style={{ fontSize:10, color:MUTED, fontWeight:700,
                  textTransform:"uppercase", letterSpacing:1, marginBottom:4 }}>{l}</div>
                <div style={{ fontSize:26, fontWeight:800, color:c,
                  fontFamily:"monospace" }}>{v}</div>
              </div>
            ))}
          </div>

          {/* ── RECOMENDAÇÃO ── */}
          <div style={{ background:CARD, border:`1px solid ${BORDER}`,
            borderRadius:12, padding:18, marginBottom:14,
            boxShadow:"0 1px 6px #00000008" }}>
            <div style={{ fontSize:11, color:GOLD, fontWeight:700,
              textTransform:"uppercase", letterSpacing:1, marginBottom:12 }}>
              Recomendação de Crédito
            </div>
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr", gap:12 }}>
              <div>
                <div style={{ fontSize:10, color:MUTED, marginBottom:3 }}>LIMITE SUGERIDO</div>
                <div style={{ fontSize:13, fontWeight:600, color:TEXT }}>{r.limite_sugerido}</div>
              </div>
              <div>
                <div style={{ fontSize:10, color:MUTED, marginBottom:3 }}>PRAZO</div>
                <div style={{ fontSize:13, fontWeight:600, color:TEXT }}>{r.prazo_sugerido}</div>
              </div>
              <div>
                <div style={{ fontSize:10, color:MUTED, marginBottom:3 }}>MONITORAMENTO</div>
                <div style={{ fontSize:13, fontWeight:600, color:TEXT }}>{r.plano_monitoramento}</div>
              </div>
              <div style={{ gridColumn:"1/-1" }}>
                <div style={{ fontSize:10, color:MUTED, marginBottom:6 }}>GARANTIAS RECOMENDADAS</div>
                <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
                  {r.garantias_recomendadas?.map((g,i)=>(
                    <span key={i} style={{ background:BG, border:`1px solid ${BORDER}`,
                      borderRadius:6, padding:"4px 12px",
                      fontSize:11, color:NAVY, fontWeight:600 }}>{g}</span>
                  ))}
                </div>
              </div>
            </div>
          </div>

          {/* ── FLAGS ── */}
          <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr 1fr",
            gap:10, marginBottom:14 }}>
            {[
              {t:`🔴 Red Flags (${r.red_flags?.length||0})`,items:r.red_flags,c:"#c0392b",bg:"#fff0ee"},
              {t:`🟡 Yellow Flags (${r.yellow_flags?.length||0})`,items:r.yellow_flags,c:"#b45309",bg:"#fff8ee"},
              {t:`🟢 Green Flags (${r.green_flags?.length||0})`,items:r.green_flags,c:"#0e7a5a",bg:"#edfaf5"},
            ].map(({t,items,c,bg})=>(
              <div key={t} style={{ background:bg, border:`1px solid ${c}33`,
                borderRadius:10, padding:14 }}>
                <div style={{ fontSize:11, fontWeight:700, color:c, marginBottom:8 }}>{t}</div>
                {!items?.length
                  ? <div style={{ fontSize:11, color:MUTED }}>Nenhum</div>
                  : items.map((f,i)=>(
                    <div key={i} style={{ fontSize:11, color:TEXT, marginBottom:4,
                      paddingLeft:8, borderLeft:`2px solid ${c}66`, lineHeight:1.5 }}>{f}</div>
                  ))
                }
              </div>
            ))}
          </div>

          {/* ── SINAIS RJ ── */}
          {r.sinais_rj?.length > 0 && (
            <div style={{ background:"#fff0ee", border:"1px solid #f5c6c6",
              borderRadius:12, padding:16, marginBottom:14 }}>
              <div style={{ fontSize:13, fontWeight:700, color:"#c0392b", marginBottom:8 }}>
                ⚠ Sinais de Stress / Recuperação Judicial
              </div>
              {r.sinais_rj.map((s,i)=>(
                <div key={i} style={{ fontSize:13, color:"#7f1d1d", marginBottom:4 }}>• {s}</div>
              ))}
            </div>
          )}

          {/* ══════════════════════════════════════════════════════════
              ANÁLISE DETALHADA — BALANÇO + CISP (RelatorioFinanceiro)
              ══════════════════════════════════════════════════════════ */}
          <RelatorioFinanceiro resultado={r} />

          {/* ── 48 FONTES ── */}
          <div style={{ background:CARD, border:`1px solid ${BORDER}`,
            borderRadius:14, overflow:"hidden", marginBottom:14,
            boxShadow:"0 2px 12px #00000011" }}>
            <div style={{ padding:"16px 20px", borderBottom:`1px solid ${BORDER}`,
              display:"flex", alignItems:"center", justifyContent:"space-between",
              flexWrap:"wrap", gap:10, background:NAVY }}>
              <div>
                <div style={{ fontSize:14, fontWeight:700, color:"#fff" }}>
                  Relatório por Fonte — P.I.L.D.E.R™
                </div>
                <div style={{ fontSize:11, color:"#94a3b8", marginTop:2 }}>
                  Clique em cada fonte para ver o detalhe completo
                </div>
              </div>
              <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
                <input value={buscaFonte} onChange={e=>setBuscaFonte(e.target.value)}
                  placeholder="Buscar fonte..."
                  style={{ background:"#ffffff22", border:"1px solid #ffffff33",
                    borderRadius:6, padding:"6px 10px", color:"#fff",
                    fontSize:12, outline:"none", width:150 }}/>
                <select value={filtroFonte} onChange={e=>setFiltroFonte(e.target.value)}
                  style={{ background:"#ffffff22", border:"1px solid #ffffff33",
                    borderRadius:6, padding:"6px 10px", color:"#fff", fontSize:12 }}>
                  <option value="todas">Todas</option>
                  <option value="confirmacao">✓ Confirmado</option>
                  <option value="ausencia">○ Sem ocorrência</option>
                  <option value="indicio">⚡ Indício</option>
                  <option value="pendente">⏳ Pendente</option>
                  <option value="nao_consultado">— Não consultado</option>
                  <option value="erro">✗ Erro</option>
                </select>
                <span style={{ fontSize:11, color:"#94a3b8", alignSelf:"center" }}>
                  {fontesFiltradas.length} fonte(s)
                </span>
              </div>
            </div>
            {fontesFiltradas.map((f,i)=>(
              <FonteRow key={f.fonte+i} fonte={f} idx={r.fontes?.indexOf(f)||i} />
            ))}
          </div>

          {/* ── MEMÓRIA DE CÁLCULO ── */}
          <details style={{ background:CARD, border:`1px solid ${BORDER}`,
            borderRadius:12, padding:16, marginBottom:16 }}>
            <summary style={{ cursor:"pointer", fontSize:12, color:MUTED,
              fontWeight:700, letterSpacing:1, textTransform:"uppercase" }}>
              Memória de Cálculo
            </summary>
            <div style={{ marginTop:10, display:"flex", gap:10, flexWrap:"wrap" }}>
              {r.memoria_calculo && Object.entries(r.memoria_calculo).map(([k,v])=>(
                <div key={k} style={{ background:BG, border:`1px solid ${BORDER}`,
                  borderRadius:8, padding:"8px 14px" }}>
                  <div style={{ fontSize:10, color:MUTED, marginBottom:2,
                    textTransform:"capitalize" }}>{k.replace(/_/g," ")}</div>
                  <div style={{ fontSize:16, fontWeight:700, fontFamily:"monospace",
                    color:typeof v==="number"&&v>0?"#0e7a5a":typeof v==="number"&&v<0?"#c0392b":MUTED }}>
                    {typeof v==="number"?(v>0?`+${v}`:v):v}
                  </div>
                </div>
              ))}
            </div>
          </details>

          {/* ── ASSINATURA ── */}
          <div style={{ textAlign:"center", padding:"12px 0",
            fontSize:11, color:MUTED, fontWeight:600, letterSpacing:1 }}>
            {ASSINATURA}
          </div>
        </>
      )}
    </div>
  );
}
