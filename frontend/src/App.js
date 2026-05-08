// src/components/PilderHero.js
// Bloco de abertura do app com identidade visual P.I.L.D.E.R™

export default function PilderHero() {
  const metodo = [
    { letra: "P", cor: "#ef4444", bg: "#450a0a", titulo: "Problema", desc: "Identificar o desvio, risco ou sinal de alerta" },
    { letra: "I", cor: "#3b82f6", bg: "#0c1a3a", titulo: "Informação", desc: "Reunir fatos, dados, histórico e evidências" },
    { letra: "L", cor: "#b45309", bg: "#2d1a02", titulo: "Leitura", desc: "Interpretar criticamente com apoio de IA e visão analítica" },
    { letra: "D", cor: "#10b981", bg: "#064e3b", titulo: "Decisão", desc: "Definir a medida mais adequada com objetividade" },
    { letra: "E", cor: "#8b5cf6", bg: "#2e1065", titulo: "Execução", desc: "Implementar a ação com disciplina e velocidade" },
    { letra: "R", cor: "#64748b", bg: "#0f172a", titulo: "Revisão", desc: "Monitorar os efeitos e recalibrar continuamente" },
  ];

  return (
    <div style={{
      background: "linear-gradient(135deg, #0a1628 0%, #0f1e3a 50%, #0a1628 100%)",
      border: "1px solid #1e3a5f",
      borderRadius: 16,
      padding: "32px 28px",
      marginBottom: 28,
      position: "relative",
      overflow: "hidden",
    }}>
      {/* Fundo decorativo */}
      <div style={{
        position: "absolute", top: -40, right: -40,
        width: 200, height: 200,
        background: "radial-gradient(circle, #b4930322 0%, transparent 70%)",
        borderRadius: "50%", pointerEvents: "none",
      }} />
      <div style={{
        position: "absolute", bottom: -30, left: -30,
        width: 150, height: 150,
        background: "radial-gradient(circle, #1e3a5f33 0%, transparent 70%)",
        borderRadius: "50%", pointerEvents: "none",
      }} />

      {/* Header com logo + texto */}
      <div style={{
        display: "flex", alignItems: "center", gap: 24,
        marginBottom: 28, flexWrap: "wrap",
      }}>
        {/* Logo */}
        <div style={{
          width: 110, height: 110, borderRadius: 16,
          background: "#fff",
          display: "flex", alignItems: "center", justifyContent: "center",
          padding: 6, flexShrink: 0,
          boxShadow: "0 4px 24px #b4930344",
          border: "2px solid #b4930366",
        }}>
          {/* SVG do logo PILDER — representação fiel do símbolo */}
          <svg viewBox="0 0 200 200" width="96" height="96">
            {/* Círculo externo dourado */}
            <circle cx="100" cy="100" r="95" fill="none" stroke="#b49303" strokeWidth="6" strokeDasharray="8 4"/>
            {/* Metade esquerda azul escuro */}
            <path d="M100 8 A92 92 0 0 0 100 192" fill="#1E3A5F" opacity="0.15"/>
            {/* Seta/gráfico de barras */}
            <rect x="42" y="110" width="14" height="35" rx="3" fill="#b49303"/>
            <rect x="62" y="90" width="14" height="55" rx="3" fill="#b49303"/>
            <rect x="82" y="70" width="14" height="75" rx="3" fill="#b49303" opacity="0.7"/>
            {/* Seta para cima */}
            <path d="M95 65 L130 30 L125 50 L145 45 L140 65 L120 60 L115 80Z" fill="#1E3A5F" opacity="0.9"/>
            {/* Letra P estilizada */}
            <text x="118" y="135" fontSize="70" fontWeight="900" fill="#1E3A5F"
              fontFamily="Georgia, serif" opacity="0.95">P</text>
            {/* Perfil humano direita */}
            <path d="M155 55 Q175 70 172 95 Q170 118 155 130 Q165 110 163 90 Q162 70 155 55Z"
              fill="#1E3A5F" opacity="0.4"/>
            {/* Circuito neural */}
            <circle cx="160" cy="80" r="3" fill="#b49303"/>
            <circle cx="170" cy="95" r="3" fill="#b49303"/>
            <circle cx="158" cy="108" r="3" fill="#b49303"/>
            <line x1="160" y1="80" x2="170" y2="95" stroke="#b49303" strokeWidth="1.5" opacity="0.7"/>
            <line x1="170" y1="95" x2="158" y2="108" stroke="#b49303" strokeWidth="1.5" opacity="0.7"/>
          </svg>
        </div>

        {/* Texto principal */}
        <div style={{ flex: 1, minWidth: 200 }}>
          <div style={{
            fontSize: 36, fontWeight: 900, letterSpacing: 4,
            color: "#1E3A5F",
            WebkitTextStroke: "1px #b49303",
            textShadow: "0 0 30px #b4930355",
            fontFamily: "Georgia, 'Times New Roman', serif",
            lineHeight: 1,
          }}>
            P.I.L.D.E.R™
          </div>
          <div style={{
            fontSize: 13, fontWeight: 700, color: "#b49303",
            letterSpacing: 2, textTransform: "uppercase",
            marginTop: 6, marginBottom: 4,
          }}>
            Método de Crédito e Cobrança
          </div>
          <div style={{
            fontSize: 11, color: "#94a3b8", letterSpacing: 1,
            textTransform: "uppercase", marginBottom: 8,
          }}>
            Com Gestão em I.A
          </div>
          {/* Badge C3 */}
          <div style={{
            display: "inline-flex", alignItems: "center", gap: 8,
            background: "#0f172a", border: "1px solid #1e3a5f",
            borderRadius: 8, padding: "6px 12px",
          }}>
            <span style={{ fontSize: 16, fontWeight: 900, color: "#1E3A5F",
              WebkitTextStroke: "0.5px #b49303" }}>C3</span>
            <span style={{ width: 1, height: 20, background: "#1e3a5f" }} />
            <span style={{ fontSize: 10, color: "#64748b", textAlign: "center", lineHeight: 1.3 }}>
              💳<br/>Crédito
            </span>
            <span style={{ fontSize: 10, color: "#64748b", textAlign: "center", lineHeight: 1.3 }}>
              💰<br/>Caixa
            </span>
            <span style={{ fontSize: 10, color: "#64748b", textAlign: "center", lineHeight: 1.3 }}>
              📊<br/>Controle
            </span>
          </div>
        </div>

        {/* Frase direita */}
        <div style={{
          background: "#0f172a", border: "1px solid #1e3a5f",
          borderRadius: 10, padding: "14px 18px", maxWidth: 220,
        }}>
          <div style={{ fontSize: 11, color: "#b49303", fontWeight: 700,
            letterSpacing: 1, marginBottom: 4 }}>TRILOGIA ESTRATÉGICA</div>
          <div style={{ fontSize: 12, color: "#94a3b8", lineHeight: 1.6 }}>
            Um framework prático para transformar <b style={{ color: "#e2e8f0" }}>dados em decisão</b> e decisão em resultado.
          </div>
        </div>
      </div>

      {/* Linha dourada separadora */}
      <div style={{
        height: 1,
        background: "linear-gradient(90deg, transparent, #b49303, transparent)",
        marginBottom: 24,
      }} />

      {/* Grid do método — 6 letras */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(6, 1fr)",
        gap: 10,
      }}>
        {metodo.map(({ letra, cor, bg, titulo, desc }) => (
          <div key={letra} style={{
            background: bg,
            border: `1px solid ${cor}44`,
            borderRadius: 10,
            padding: "14px 10px",
            textAlign: "center",
            transition: "transform 0.2s, box-shadow 0.2s",
            cursor: "default",
          }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-3px)";
              e.currentTarget.style.boxShadow = `0 8px 24px ${cor}33`;
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "none";
            }}
          >
            <div style={{
              fontSize: 28, fontWeight: 900, color: cor,
              fontFamily: "Georgia, serif",
              lineHeight: 1, marginBottom: 6,
              textShadow: `0 0 20px ${cor}66`,
            }}>{letra}</div>
            <div style={{
              fontSize: 11, fontWeight: 700, color: cor,
              marginBottom: 6, letterSpacing: 0.5,
            }}>{titulo}</div>
            <div style={{
              fontSize: 10, color: "#64748b", lineHeight: 1.4,
            }}>{desc}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
