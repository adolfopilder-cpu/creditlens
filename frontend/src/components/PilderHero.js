// src/components/PilderHero.js
export default function PilderHero() {
  const metodo = [
    { letra: "P", cor: "#ef4444", bg: "#450a0a", titulo: "Problema",
      desc: "Entender corretamente o que realmente está sendo analisado." },
    { letra: "I", cor: "#3b82f6", bg: "#0c1a3a", titulo: "Informação",
      desc: "Coletar dados relevantes e confiáveis para a decisão." },
    { letra: "L", cor: "#b45309", bg: "#2d1a02", titulo: "Leitura",
      desc: "Transformar dados em diagnóstico e interpretação de risco." },
    { letra: "D", cor: "#10b981", bg: "#064e3b", titulo: "Decisão",
      desc: "Definir a melhor estrutura de crédito com consciência do risco." },
    { letra: "E", cor: "#8b5cf6", bg: "#2e1065", titulo: "Execução",
      desc: "Garantir que a decisão seja aplicada e monitorada corretamente." },
    { letra: "R", cor: "#b49303", bg: "#1a1400", titulo: "Revisão",
      desc: "Reavaliar continuamente o comportamento e o nível de risco." },
  ];

  return (
    <div style={{
      background: "linear-gradient(135deg, #0a1628 0%, #0f1e3a 50%, #0a1628 100%)",
      border: "1px solid #1e3a5f", borderRadius: 16,
      padding: "32px 28px", marginBottom: 28,
      position: "relative", overflow: "hidden",
    }}>
      {/* Decorativos */}
      <div style={{ position:"absolute", top:-40, right:-40, width:200, height:200,
        background:"radial-gradient(circle, #b4930322 0%, transparent 70%)",
        borderRadius:"50%", pointerEvents:"none" }} />
      <div style={{ position:"absolute", bottom:-30, left:-30, width:150, height:150,
        background:"radial-gradient(circle, #1e3a5f33 0%, transparent 70%)",
        borderRadius:"50%", pointerEvents:"none" }} />

      {/* Header logo + texto */}
      <div style={{ display:"flex", alignItems:"center", gap:24, marginBottom:24, flexWrap:"wrap" }}>

        {/* Logo REAL */}
        <div style={{
          width:130, height:130, borderRadius:16, background:"#fff",
          display:"flex", alignItems:"center", justifyContent:"center",
          padding:8, flexShrink:0,
          boxShadow:"0 4px 32px #b4930366", border:"2px solid #b49303",
        }}>
          <img
            src="/P_I_L_D_E_R__fundo_branco.jpeg"
            alt="P.I.L.D.E.R™"
            style={{
              width:"100%", height:"100%",
              objectFit:"contain", borderRadius:10,
            }}
          />
        </div>

        {/* Texto principal */}
        <div style={{ flex:1, minWidth:200 }}>
          <div style={{
            fontSize:36, fontWeight:900, letterSpacing:4,
            color:"#e2e8f0",
            textShadow:"0 0 30px #b4930555",
            fontFamily:"Georgia, 'Times New Roman', serif", lineHeight:1,
          }}>
            P.I.L.D.E.R™
          </div>
          <div style={{ fontSize:13, fontWeight:700, color:"#b49303",
            letterSpacing:2, textTransform:"uppercase", marginTop:6, marginBottom:4 }}>
            Método de Crédito e Cobrança
          </div>
          <div style={{ fontSize:11, color:"#94a3b8", letterSpacing:1,
            textTransform:"uppercase", marginBottom:12 }}>
            Com Gestão em I.A
          </div>
          {/* Badge C3 */}
          <div style={{ display:"inline-flex", alignItems:"center", gap:10,
            background:"#0f172a", border:"1px solid #1e3a5f",
            borderRadius:8, padding:"8px 14px" }}>
            <span style={{ fontSize:18, fontWeight:900, color:"#e2e8f0",
              WebkitTextStroke:"0.5px #b49303", fontFamily:"Georgia,serif" }}>C3</span>
            <span style={{ width:1, height:24, background:"#1e3a5f" }} />
            <span style={{ fontSize:11, color:"#64748b", textAlign:"center", lineHeight:1.5 }}>💳<br/>Crédito</span>
            <span style={{ fontSize:11, color:"#64748b", textAlign:"center", lineHeight:1.5 }}>💰<br/>Caixa</span>
            <span style={{ fontSize:11, color:"#64748b", textAlign:"center", lineHeight:1.5 }}>📊<br/>Controle</span>
          </div>
        </div>

        {/* Card direita */}
        <div style={{ background:"#0f172a", border:"1px solid #1e3a5f",
          borderRadius:12, padding:"16px 20px", maxWidth:240 }}>
          <div style={{ fontSize:11, color:"#b49303", fontWeight:700,
            letterSpacing:1.2, textTransform:"uppercase", marginBottom:8 }}>
            Trilogia Estratégica
          </div>
          <div style={{ fontSize:13, color:"#94a3b8", lineHeight:1.7 }}>
            Um framework prático para transformar{" "}
            <b style={{ color:"#e2e8f0" }}>dados em decisão</b>{" "}
            e decisão em resultado.
          </div>
        </div>
      </div>

      {/* Linha dourada */}
      <div style={{ height:1,
        background:"linear-gradient(90deg,transparent,#b49303,transparent)",
        marginBottom:22 }} />

      {/* Grid 6 cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(6,1fr)", gap:10, marginBottom:20 }}>
        {metodo.map(({ letra, cor, bg, titulo }) => (
          <div key={letra} style={{
            background:bg, border:`1px solid ${cor}55`,
            borderRadius:10, padding:"16px 10px", textAlign:"center",
            transition:"transform 0.2s, box-shadow 0.2s", cursor:"default",
          }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-4px)";
              e.currentTarget.style.boxShadow = `0 10px 28px ${cor}44`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <div style={{ fontSize:32, fontWeight:900, color:cor,
              fontFamily:"Georgia,serif", lineHeight:1, marginBottom:6,
              textShadow:`0 0 20px ${cor}88` }}>{letra}</div>
            <div style={{ fontSize:11, fontWeight:700, color:cor,
              letterSpacing:0.5 }}>{titulo}</div>
          </div>
        ))}
      </div>

      {/* Lista detalhada */}
      <div style={{ background:"#0f172a", border:"1px solid #1e3a5f",
        borderRadius:12, padding:"18px 22px" }}>
        <div style={{ fontSize:11, color:"#b49303", fontWeight:700,
          letterSpacing:1.2, textTransform:"uppercase", marginBottom:16 }}>
          Como o Método Funciona
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:12 }}>
          {metodo.map(({ letra, cor, titulo, desc }) => (
            <div key={letra} style={{ display:"flex", alignItems:"flex-start", gap:14 }}>
              <div style={{
                width:34, height:34, borderRadius:8, flexShrink:0,
                background:`${cor}22`, border:`1px solid ${cor}55`,
                display:"flex", alignItems:"center", justifyContent:"center",
                fontSize:18, fontWeight:900, color:cor,
                fontFamily:"Georgia,serif",
              }}>{letra}</div>
              <div style={{ flex:1, paddingTop:4 }}>
                <span style={{ fontSize:13, fontWeight:700, color:cor }}>
                  {letra} — {titulo}
                </span>
                <span style={{ fontSize:13, color:"#94a3b8" }}>
                  {" "}👉 {desc}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Assinatura */}
      <div style={{ marginTop:16, textAlign:"center", fontSize:10,
        color:"#334155", letterSpacing:1.2, fontWeight:600,
        textTransform:"uppercase" }}>
        P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito
      </div>
    </div>
  );
}
