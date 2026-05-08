// src/components/ui.js — componentes visuais compartilhados

export const RATING_ORDER = ["AAA","AA","A","BBB","BB","B","C","D"];
export const RATING_COLOR = {
  AAA:"#10b981", AA:"#34d399", A:"#6ee7b7",
  BBB:"#fbbf24", BB:"#f59e0b", B:"#f97316",
  C:"#ef4444", D:"#7f1d1d"
};
export const RISCO_COLOR = { baixo:"#10b981", medio:"#f59e0b", alto:"#ef4444" };
export const CONECTOR_COLOR = {
  ativo:"#10b981", ativo_parcial:"#f59e0b",
  pendente:"#64748b", erro:"#ef4444"
};

export function ScoreBadge({ score }) {
  const color = score >= 75 ? "#10b981" : score >= 50 ? "#f59e0b" : "#ef4444";
  const bg = score >= 75 ? "#064e3b" : score >= 50 ? "#451a03" : "#450a0a";
  const deg = score * 3.6;
  return (
    <div style={{ display:"inline-flex", alignItems:"center", gap:8,
      background:bg, borderRadius:8, padding:"4px 12px",
      border:`1px solid ${color}33` }}>
      <svg width="32" height="32" viewBox="0 0 32 32">
        <circle cx="16" cy="16" r="13" fill="none" stroke="#1e293b" strokeWidth="3"/>
        <circle cx="16" cy="16" r="13" fill="none" stroke={color} strokeWidth="3"
          strokeDasharray={`${(deg/360)*81.68} 81.68`}
          strokeDashoffset="20.42" strokeLinecap="round"/>
        <text x="16" y="21" textAnchor="middle" fill={color}
          fontSize="10" fontWeight="700" fontFamily="monospace">{score}</text>
      </svg>
    </div>
  );
}

export function RatingBadge({ rating }) {
  const color = RATING_COLOR[rating] || "#94a3b8";
  return (
    <span style={{ background:`${color}22`, color, border:`1px solid ${color}44`,
      borderRadius:5, padding:"2px 9px", fontWeight:700, fontSize:12,
      fontFamily:"monospace", letterSpacing:1 }}>{rating}</span>
  );
}

export function RiscoTag({ risco }) {
  const color = RISCO_COLOR[risco] || "#94a3b8";
  const label = { baixo:"Baixo", medio:"Médio", alto:"Alto" }[risco] || risco;
  return (
    <span style={{ background:`${color}18`, color, border:`1px solid ${color}33`,
      borderRadius:4, padding:"2px 9px", fontSize:11, fontWeight:600 }}>{label}</span>
  );
}

export function ConectorBadge({ status }) {
  const color = CONECTOR_COLOR[status] || "#64748b";
  const label = { ativo:"✓ Ativo", ativo_parcial:"⚡ Parcial",
    pendente:"○ Pendente", erro:"✗ Erro" }[status] || status;
  return (
    <span style={{ background:`${color}18`, color, border:`1px solid ${color}33`,
      borderRadius:20, padding:"2px 10px", fontSize:11, fontWeight:700 }}>{label}</span>
  );
}

export function KpiCard({ label, value, sub, color="#e2e8f0" }) {
  return (
    <div style={{ background:"#0f172a", border:"1px solid #1e293b",
      borderRadius:12, padding:"18px 22px", flex:1, minWidth:130 }}>
      <div style={{ fontSize:10, color:"#64748b", fontWeight:700,
        letterSpacing:1.2, textTransform:"uppercase", marginBottom:6 }}>{label}</div>
      <div style={{ fontSize:28, fontWeight:800, color,
        fontFamily:"monospace", lineHeight:1 }}>{value}</div>
      {sub && <div style={{ fontSize:11, color:"#475569", marginTop:5 }}>{sub}</div>}
    </div>
  );
}

export function Spinner() {
  return (
    <div style={{ display:"flex", alignItems:"center", justifyContent:"center", padding:40 }}>
      <div style={{ width:32, height:32, border:"3px solid #1e293b",
        borderTop:"3px solid #3b82f6", borderRadius:"50%",
        animation:"spin 0.8s linear infinite" }}/>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

export function FlagList({ title, items, color }) {
  return (
    <div style={{ background:"#0f172a", borderRadius:10, padding:14 }}>
      <div style={{ fontSize:11, fontWeight:700, color, marginBottom:10, letterSpacing:0.5 }}>{title}</div>
      {!items?.length
        ? <div style={{ fontSize:12, color:"#334155" }}>Nenhum apontamento</div>
        : items.map((f, i) => (
          <div key={i} style={{ fontSize:11, color:"#64748b", marginBottom:5,
            paddingLeft:8, borderLeft:`2px solid ${color}55` }}>{f}</div>
        ))
      }
    </div>
  );
}
