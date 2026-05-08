// src/components/PilderHero.js
export default function PilderHero() {
  const BG = "#f5f0e8";
  const CARD = "#ffffff";
  const BORDER = "#d4c9a8";
  const NAVY = "#1E3A5F";
  const GOLD = "#b49303";
  const MUTED = "#6b6b7b";

  const metodo = [
    { letra: "P", cor: "#c0392b", bg: "#fff0ee", titulo: "Problema",
      desc: "Entender corretamente o que realmente está sendo analisado." },
    { letra: "I", cor: "#1E3A5F", bg: "#eef3fa", titulo: "Informação",
      desc: "Coletar dados relevantes e confiáveis para a decisão." },
    { letra: "L", cor: "#b45309", bg: "#fff8ee", titulo: "Leitura",
      desc: "Transformar dados em diagnóstico e interpretação de risco." },
    { letra: "D", cor: "#0e7a5a", bg: "#edfaf5", titulo: "Decisão",
      desc: "Definir a melhor estrutura de crédito com consciência do risco." },
    { letra: "E", cor: "#6d28d9", bg: "#f5f0ff", titulo: "Execução",
      desc: "Garantir que a decisão seja aplicada e monitorada corretamente." },
    { letra: "R", cor: "#b49303", bg: "#fdfbee", titulo: "Revisão",
      desc: "Reavaliar continuamente o comportamento e o nível de risco." },
  ];

  return (
    <div style={{ background: CARD, border: `1px solid ${BORDER}`,
      borderRadius: 16, padding: "32px 28px", marginBottom: 24,
      boxShadow: "0 2px 16px #00000011" }}>

      {/* Header logo + texto */}
      <div style={{ display: "flex", alignItems: "center", gap: 24,
        marginBottom: 24, flexWrap: "wrap" }}>

        {/* Logo real */}
        <div style={{ width: 140, height: 140, borderRadius: 16,
          background: "#fff", display: "flex", alignItems: "center",
          justifyContent: "center", padding: 8, flexShrink: 0,
          boxShadow: `0 4px 24px ${GOLD}44`,
          border: `2px solid ${GOLD}` }}>
          <img
            src="/P_I_L_D_E_R__fundo_branco.jpeg"
            alt="P.I.L.D.E.R™"
            onError={e => { e.target.style.display="none"; }}
            style={{ width: "100%", height: "100%",
              objectFit: "contain", borderRadius: 10 }}
          />
        </div>

        {/* Texto */}
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{ fontSize: 38, fontWeight: 900, letterSpacing: 4,
            color: NAVY, fontFamily: "Georgia, serif", lineHeight: 1,
            textShadow: `2px 2px 0px ${GOLD}44` }}>
            P.I.L.D.E.R™
          </div>
          <div style={{ fontSize: 14, fontWeight: 700, color: GOLD,
            letterSpacing: 2, textTransform: "uppercase", marginTop: 6, marginBottom: 4 }}>
            Método de Crédito e Cobrança
          </div>
          <div style={{ fontSize: 12, color: MUTED, letterSpacing: 1,
            textTransform: "uppercase", marginBottom: 14 }}>
            Com Gestão em I.A
          </div>
          {/* Badge C3 */}
          <div style={{ display: "inline-flex", alignItems: "center", gap: 10,
            background: BG, border: `1px solid ${BORDER}`,
            borderRadius: 10, padding: "8px 16px" }}>
            <span style={{ fontSize: 20, fontWeight: 900, color: NAVY,
              fontFamily: "Georgia,serif" }}>C3</span>
            <span style={{ width: 1, height: 28, background: BORDER }} />
            <span style={{ fontSize: 11, color: MUTED, textAlign: "center", lineHeight: 1.5 }}>💳<br/>Crédito</span>
            <span style={{ fontSize: 11, color: MUTED, textAlign: "center", lineHeight: 1.5 }}>💰<br/>Caixa</span>
            <span style={{ fontSize: 11, color: MUTED, textAlign: "center", lineHeight: 1.5 }}>📊<br/>Controle</span>
          </div>
        </div>

        {/* Card direita */}
        <div style={{ background: NAVY, borderRadius: 14,
          padding: "18px 22px", maxWidth: 240 }}>
          <div style={{ fontSize: 11, color: GOLD, fontWeight: 700,
            letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 8 }}>
            Trilogia Estratégica
          </div>
          <div style={{ fontSize: 13, color: "#cbd5e1", lineHeight: 1.7 }}>
            Um framework prático para transformar{" "}
            <b style={{ color: "#fff" }}>dados em decisão</b>{" "}
            e decisão em resultado.
          </div>
        </div>
      </div>

      {/* Linha dourada */}
      <div style={{ height: 2,
        background: `linear-gradient(90deg, transparent, ${GOLD}, transparent)`,
        marginBottom: 22 }} />

      {/* Grid 6 cards */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(6,1fr)",
        gap: 10, marginBottom: 22 }}>
        {metodo.map(({ letra, cor, bg, titulo }) => (
          <div key={letra} style={{ background: bg,
            border: `2px solid ${cor}33`, borderRadius: 12,
            padding: "16px 10px", textAlign: "center",
            transition: "transform 0.2s, box-shadow 0.2s", cursor: "default",
            boxShadow: "0 2px 8px #00000011" }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-4px)";
              e.currentTarget.style.boxShadow = `0 10px 28px ${cor}33`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 2px 8px #00000011";
            }}>
            <div style={{ fontSize: 34, fontWeight: 900, color: cor,
              fontFamily: "Georgia,serif", lineHeight: 1, marginBottom: 6 }}>
              {letra}
            </div>
            <div style={{ fontSize: 11, fontWeight: 700, color: cor,
              letterSpacing: 0.5 }}>{titulo}</div>
          </div>
        ))}
      </div>

      {/* Lista detalhada */}
      <div style={{ background: BG, border: `1px solid ${BORDER}`,
        borderRadius: 12, padding: "20px 24px" }}>
        <div style={{ fontSize: 11, color: GOLD, fontWeight: 700,
          letterSpacing: 1.2, textTransform: "uppercase", marginBottom: 16 }}>
          Como o Método Funciona
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          {metodo.map(({ letra, cor, titulo, desc }) => (
            <div key={letra} style={{ display: "flex",
              alignItems: "flex-start", gap: 14 }}>
              <div style={{ width: 36, height: 36, borderRadius: 9,
                flexShrink: 0, background: `${cor}18`,
                border: `2px solid ${cor}44`,
                display: "flex", alignItems: "center",
                justifyContent: "center", fontSize: 18, fontWeight: 900,
                color: cor, fontFamily: "Georgia,serif" }}>
                {letra}
              </div>
              <div style={{ flex: 1, paddingTop: 6 }}>
                <span style={{ fontSize: 14, fontWeight: 700, color: cor }}>
                  {letra} — {titulo}
                </span>
                <span style={{ fontSize: 14, color: MUTED }}>
                  {" "}👉 {desc}
                </span>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Assinatura */}
      <div style={{ marginTop: 16, textAlign: "center", fontSize: 11,
        color: MUTED, letterSpacing: 1, fontWeight: 600 }}>
        P.I.L.D.E.R™ – Método Estruturado de Análise e Gestão de Crédito
      </div>
    </div>
  );
}
