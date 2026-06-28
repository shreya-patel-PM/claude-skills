import { useState, useRef, useEffect } from "react";

// ─── DESIGN TOKENS ───
const T = {
  bg: "#08090D", surface: "#111318", card: "#1A1D27", elevated: "#242836",
  border: "#2D3141", borderLight: "#383D52",
  accent: "#FF6B35", mint: "#00E599", purple: "#8B5CF6", coral: "#FF7EB3", amber: "#FBBF24",
  text: "#F5F3FF", textSec: "#9CA0B0", textMuted: "#5C6070",
  glow: "rgba(255,107,53,0.15)", mintGlow: "rgba(0,229,153,0.12)",
};
const DOMAIN_COLORS = { streaming: T.amber, pm: T.purple, pharma: T.coral, ads: "#F97316", product: T.accent };
const DOMAIN_LABELS = { streaming: "Streaming", pm: "Product Mgmt", pharma: "Pharma", ads: "Ad Revenue", product: "Product" };

const SHREYA_CONTEXT = `You are Shreya Patel's portfolio AI assistant. Answer questions conversationally and confidently — as her professional representative. Keep answers concise (2-4 sentences) unless detail is requested.

CRITICAL RULES:
- Only 3 agents are SHIPPED and live. The other 18 are PLANNED but NOT yet built.
- NEVER describe a planned agent as if it is complete or shipped.
- If asked "what has she shipped," ONLY mention the 3 shipped agents below.

CURRENT ROLE: Senior Product Manager at Eli Lilly (Cancer Clinical Platform). Building StreamMind — a 22-week project to ship 21 AI agents (reduced from 24 for depth over breadth). Currently Week 7 of 22.

STREAMMIND: 21 agents total — 11 streaming, 3 ad-revenue, 5 PM, 1 pharma, 1 product (AutoApply). 4 are FLAGSHIP-grade with full evals, architecture docs, guardrails, and cost analysis. Stack: Claude API, Make, Airtable, Notion, Supabase, CrewAI, Streamlit, Vercel, GitHub Actions, Next.js.

4 FLAGSHIPS (deep architecture + evals + guardrails):
1. AutoApply — Ghost job detection SaaS. Next.js + Supabase + Claude classification. Full F1 eval, adversarial benchmark, GUARDRAILS.md.
2. Clinical Trial Analyzer (Pharma) — RAG over trial PDFs. Guardrails for regulated domain.
3. Ad Incrementality Brief (Streaming #19) — Deterministic lift math + LLM narration. "When NOT to use an agent" example.
4. PM Copilot (PM #5) — CrewAI multi-agent (Researcher/Writer/Reviewer) + Supabase memory + Slack Bolt.

3 SHIPPED AGENTS:
1. Grooming Bot (PM #1) — JIRA story grooming. LLM: Claude Sonnet, Framework: Make, No RAG. Shipped Week 3.
2. Research Synthesizer (PM #2) — Research to product insights. LLM: Claude Sonnet, Framework: Make+Streamlit, No RAG. Shipped Week 6.
3. Monday Weekly Digest (Streaming #13) — Weekly email digest. LLM: Claude Sonnet, Framework: Make, No RAG. Shipped Week 6.

18 PLANNED (NOT yet built): target all 21 by September 2026. Cut 3 agents from original 24 plan (release readiness, localization brief, compliance watch) for redundancy — chose depth over breadth.

WORK: Eli Lilly Sr PM Jan 2026–Present, T-Mobile Sr PO (27% adoption↑), J&J PO, CVS Aetna PM (100% migration), Salesforce PO (60K users, 40% adoption↑), MUFG PO, Stylekart Analyst.

SALESFORCE DEEP DIVE (Feb 2021–Mar 2023):
- V2MOM Application: 70K+ employees, AppExchange, 95% alignment, 10+ mgmt layers, 6+ features
- Insiders Program: 300+ volunteers, 19 countries, 97% offer acceptance, 2,483 sessions
- Camp B-Well: 5 wellness dimensions, 5+ Trailhead modules
- Impact: 40% adoption↑, 60K users, 6 certs, 13 Superbadges

EDUCATION: Northwestern Kellogg PM 2022, MS MIS Cal State Fullerton 2017, BS IT Mumbai 2013.
CERTS: 6 Salesforce+13 Superbadges, Oracle SQL/PLSQL, CSPO, CSM, SAFe.
CONTACT: shreyaishwarlalpatel@gmail.com, 415-604-6080, linkedin.com/in/shreeapatel, github.com/shreya-patel-PM

If unsure, say so and suggest emailing her directly.`;

const AGENTS = [
  // ── Streaming (11) ──
  {id:1,name:"Content Tagging",domain:"streaming",desc:"Auto-tags catalog titles with genre, mood, and audience metadata via structured JSON",stack:"Airtable catalog → Make → Claude tags as JSON → Airtable writeback",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Tag accuracy vs human baseline",framework:"Make"},
  {id:2,name:"Copy Generator",domain:"streaming",desc:"Generates 6 marketing copy variants from a content brief",stack:"Notion brief → Make → Claude 6 variants JSON → Notion + Slack #copy-review",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Variant quality + tone consistency",framework:"Make"},
  {id:3,name:"Subtitle QA",domain:"streaming",desc:"Watches for new SRT files and validates quality automatically",stack:"Google Drive SRT watcher → Make → Claude QA → Airtable error log + Slack",shipped:false,llm:"Claude Haiku",rag:false,evals:"Error detection accuracy",framework:"Make"},
  {id:4,name:"Churn Risk Scorer",domain:"streaming",desc:"Scores subscribers on churn risk from engagement signals, triggers retention emails",stack:"Subscriber sheet → Make → Claude risk scoring → Mailchimp retention email",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Precision/recall on churn labels",framework:"Make"},
  {id:5,name:"Win-Back Campaign",domain:"streaming",desc:"Generates personalized re-engagement sequences for churned users",stack:"Airtable cancellation log → Make → Claude → Mailchimp journey",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Open rate + reactivation tracking",framework:"Make"},
  {id:6,name:"Content Gap Analyzer",domain:"streaming",desc:"Identifies missing content categories by analyzing search queries",stack:"Query data → Make → Claude gap report → Notion",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Gap relevance scoring",framework:"Make"},
  {id:7,name:"A/B Test Analyzer",domain:"streaming",desc:"Reads experiment results from Sheets and generates analysis memos",stack:"Sheets trigger → Make → Claude analysis JSON → Notion memo + Slack",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Statistical conclusion accuracy",framework:"Make"},
  {id:8,name:"Licensing Monitor",domain:"streaming",desc:"Monitors content contracts and generates renewal briefs",stack:"Airtable contracts → Make Monday scheduler → Claude renewal brief → Gmail + Slack",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Date accuracy + brief completeness",framework:"Make"},
  {id:9,name:"Monday Weekly Digest",domain:"streaming",desc:"Automated weekly content digest delivered every Monday via email",stack:"Make Monday 7am → Google Sheets data → Claude 300-word digest → Gmail",shipped:true,llm:"Claude Sonnet",rag:false,evals:"Content accuracy + formatting",framework:"Make"},
  {id:10,name:"Rec Eval Agent",domain:"streaming",desc:"Evaluates recommendation engine outputs against viewing history",stack:"Rec API output → Make → Claude relevance scoring → Airtable report",shipped:false,llm:"Claude Sonnet",rag:true,evals:"NDCG + relevance scoring",framework:"Make"},
  {id:11,name:"Personalized Digest",domain:"streaming",desc:"Per-subscriber personalized content digests based on watch history",stack:"User profiles → Make → Claude personalization → Email delivery",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Personalization relevance + engagement",framework:"Make"},
  // ── Ad Revenue (3) ──
  {id:12,name:"Ad Incrementality Brief",domain:"ads",desc:"Generates incrementality lift reports — deterministic stats calc with LLM narration",stack:"Experiment data → Python lift math → Claude narrative → Notion report",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Lift accuracy + narrative quality",framework:"Make + Python",flagship:true},
  {id:13,name:"Contextual Ad Slate Matcher",domain:"ads",desc:"Matches ad inventory to content context for optimal slate placement",stack:"Content metadata + ad catalog → Make → Claude matching → Airtable slate",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Relevance scoring + fill rate",framework:"Make"},
  {id:14,name:"Ad Creative Variant Generator",domain:"ads",desc:"Generates ad copy variants tailored to content and audience segments",stack:"Campaign brief → Make → Claude variants → Slack #ad-review",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Brand safety + variant diversity",framework:"Make"},
  // ── PM (5) ──
  {id:15,name:"Grooming Bot",domain:"pm",desc:"Automates JIRA story grooming with acceptance criteria, edge cases & sizing",stack:"JIRA webhook → Make → Claude structured generation → JIRA update",shipped:true,llm:"Claude Sonnet",rag:false,evals:"Output quality + edge case coverage",framework:"Make"},
  {id:16,name:"Research Synthesizer",domain:"pm",desc:"Structures research transcripts into product insights and recommendations",stack:"Google Drive transcripts → Make → Claude synthesis → Streamlit dashboard",shipped:true,llm:"Claude Sonnet",rag:false,evals:"Insight relevance + completeness",framework:"Make + Streamlit"},
  {id:17,name:"PRD Studio",domain:"pm",desc:"Multi-mode PRD generator: brief → outline → full doc with edge cases and metrics",stack:"Notion brief → Make → Claude multi-pass → Notion PRD + Slack",shipped:false,llm:"Claude Sonnet",rag:false,evals:"Completeness + section quality scoring",framework:"Make"},
  {id:18,name:"Competitive Intel Hub",domain:"pm",desc:"Weekly competitive landscape digest with strategic implications",stack:"GitHub Actions Monday cron → Claude web_search → Resend digest",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Source coverage + insight quality",framework:"GitHub Actions"},
  {id:19,name:"PM Copilot",domain:"pm",desc:"Multi-agent orchestration for end-to-end PM decision support",stack:"CrewAI (Researcher/Writer/Reviewer) + Notion + Slack Bolt + Supabase memory",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Decision quality + agent coordination",framework:"CrewAI + Supabase",flagship:true},
  // ── Pharma (1) ──
  {id:20,name:"Clinical Trial Analyzer",domain:"pharma",desc:"Surfaces eligibility criteria & endpoint data from trial protocol PDFs",stack:"Google Drive PDFs → Make → Claude doc API with citations → Notion + Airtable log",shipped:false,llm:"Claude Sonnet",rag:true,evals:"Extraction accuracy + completeness",framework:"Claude Doc API",flagship:true},
  // ── Product (1) ──
  {id:21,name:"AutoApply",domain:"product",desc:"Ghost job detection SaaS — classifies listings as real vs ghost with F1-scored evals",stack:"Next.js + Supabase + Claude classification → adversarial benchmark (75 examples)",shipped:false,llm:"Claude Sonnet",rag:false,evals:"F1 score at threshold 0.60 + adversarial benchmark",framework:"Next.js + Supabase",flagship:true},
];

const EXPERIENCE = [
  {co:"Eli Lilly",role:"Senior Product Manager",dates:"Jan 2026 – Present",loc:"Remote",what:"Cancer Clinical Platform",highlight:"AI/ML-enabled clinical workflows",bullets:["Defining requirements for AI/ML-enabled solutions across clinical platform","Built AI tools to standardize BA skills across teams","Mentoring weekly in AI/ML business analysis methodologies"]},
  {co:"T-Mobile",role:"Senior Product Owner",dates:"Apr 2024 – Feb 2025",loc:"Remote",what:"Two-sided SaaS Platform",highlight:"27% adoption increase",bullets:["Owned API integration requirements and developer workflows","Wrote technical specs, epics, and acceptance criteria","Measured impact via telemetry; iterated based on data"]},
  {co:"Johnson & Johnson",role:"Product Owner",dates:"Oct 2023 – Mar 2024",loc:"Remote",what:"Clinical & Service Products",highlight:"Reduced spec ambiguity & rework",bullets:["Defined scalable technical requirements with engineering","Led customer research and competitive analysis"]},
  {co:"CVS Aetna",role:"Healthcare PM / Scrum Master",dates:"Mar 2023 – Oct 2023",loc:"Remote",what:"Data Cloud Migration",highlight:"100% migration success rate",bullets:["Led clinical data migration to Salesforce Data Cloud","Implemented AI-supported QA validation models"]},
  {co:"Salesforce",role:"Product Owner",dates:"Feb 2021 – Mar 2023",loc:"SF, CA",what:"Force.com & Service Cloud",highlight:"40% feature adoption increase",bullets:["Led V2MOM Application redesign — goal-alignment platform serving 70,000+ employees across 10+ management layers","Shipped V2MOM V2 to AppExchange as open-source Salesforce Labs solution with 6+ features","Launched Insiders Program — 300+ volunteers, 19 countries, 97% offer acceptance, 2,483 sessions","Designed Camp B-Well wellness program across 5 dimensions; produced 5+ Trailhead modules","Managed SaaS apps supporting 60K users; owned API specs, usage analytics, and performance benchmarks"]},
  {co:"MUFG Union Bank",role:"Product Owner",dates:"Mar 2017 – Jan 2021",loc:"SD, CA",what:"Sales Cloud CRM",highlight:"API-centric CRM transformation",bullets:["Coordinated API integrations between banking and customer platforms"]},
  {co:"Stylekart",role:"Product Analyst",dates:"Oct 2013 – Jun 2015",loc:"Mumbai",what:"E-commerce Analytics",highlight:"30-40% sales increase via A/B testing",bullets:["Data analysis and A/B testing insights","Social campaigns → 50% traffic increase"]},
];

const STACK = ["Claude API","Make","CrewAI","Airtable","Supabase","Notion","Streamlit","Vercel","GitHub Actions","Slack API","Reddit API","Mailchimp","Google Sheets"];
const jumpTo = (id) => document.getElementById(id)?.scrollIntoView({ behavior:"smooth" });

// ─── COMPONENTS ───

function Hero() {
  const shipped = AGENTS.filter(a => a.shipped).length;
  const stats = [
    { n:"21", label:"AI Agents", color:T.accent },
    { n:`${shipped}`, label:"Shipped", color:T.mint },
    { n:"4", label:"Flagships", color:T.coral },
    { n:"10+", label:"Years PM", color:T.amber },
  ];
  const jumps = [
    { label:"AI Agents", target:"agents" },
    { label:"Experience", target:"career" },
    { label:"Salesforce", target:"salesforce" },
    { label:"Skills", target:"skills" },
  ];
  return (
    <section style={{ padding:"48px 24px 40px", position:"relative", overflow:"hidden" }}>
      <div style={{ position:"absolute", inset:0, background:`radial-gradient(ellipse 80% 60% at 20% 40%, rgba(255,107,53,0.06) 0%, transparent 70%), radial-gradient(ellipse 60% 50% at 80% 60%, rgba(139,92,246,0.05) 0%, transparent 70%)`, pointerEvents:"none" }} />
      <div style={{ position:"relative", textAlign:"center", maxWidth:800, margin:"0 auto" }}>
        <h1 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:"clamp(40px,7vw,64px)", fontWeight:700, color:T.text, letterSpacing:"-0.04em", lineHeight:1, margin:"0 0 10px" }}>Shreya Patel</h1>
        <p style={{ fontFamily:"'Inter',sans-serif", fontSize:"clamp(15px,2.2vw,20px)", color:T.textSec, margin:"0 0 6px" }}>
          Senior Product Manager who <span style={{ color:T.accent, fontWeight:600 }}>actually builds things</span>
        </p>
        <p style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textMuted, margin:"0 0 24px" }}>
          shreyaishwarlalpatel@gmail.com · 415-604-6080 ·{" "}
          <a href="https://www.linkedin.com/in/shreeapatel/" style={{ color:T.accent, textDecoration:"none" }}>LinkedIn</a> ·{" "}
          <a href="https://github.com/shreya-patel-PM" style={{ color:T.accent, textDecoration:"none" }}>GitHub</a>
        </p>
        <div style={{ display:"flex", justifyContent:"center", gap:28, flexWrap:"wrap", marginBottom:24 }}>
          {stats.map((s,i) => (
            <div key={i} style={{ textAlign:"center" }}>
              <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:32, fontWeight:700, color:s.color, lineHeight:1 }}>{s.n}</div>
              <div style={{ fontFamily:"'Inter',sans-serif", fontSize:11, color:T.textMuted, marginTop:2, textTransform:"uppercase", letterSpacing:"0.08em" }}>{s.label}</div>
            </div>
          ))}
        </div>
        <div style={{ display:"flex", justifyContent:"center", gap:8, flexWrap:"wrap" }}>
          {jumps.map(l => (
            <button key={l.target} onClick={() => jumpTo(l.target)}
              style={{ padding:"7px 18px", fontSize:13, fontWeight:600, color:T.text, background:T.surface, border:`1px solid ${T.border}`, borderRadius:100, cursor:"pointer", fontFamily:"'Inter',sans-serif", transition:"all 0.2s" }}
              onMouseEnter={e => { e.currentTarget.style.borderColor=T.accent; e.currentTarget.style.color=T.accent }}
              onMouseLeave={e => { e.currentTarget.style.borderColor=T.border; e.currentTarget.style.color=T.text }}>
              {l.label} ↓
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}

function StreamMindSection() {
  const [filter, setFilter] = useState("all");
  const [open, setOpen] = useState(null);
  const shipped = AGENTS.filter(a => a.shipped).length;
  const filtered = filter === "all" ? AGENTS : AGENTS.filter(a => a.domain === filter);
  const total = AGENTS.length;
  const pct = Math.round((shipped / total) * 100);

  const Tag = ({ label, value, color }) => (
    <div style={{ display:"flex", alignItems:"center", gap:5 }}>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:T.textMuted, textTransform:"uppercase", letterSpacing:"0.04em", minWidth:55 }}>{label}</span>
      <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:color||T.textSec, padding:"2px 8px", background:`${(color||T.textSec)}12`, border:`1px solid ${(color||T.textSec)}25`, borderRadius:4 }}>{value}</span>
    </div>
  );

  return (
    <section style={{ padding:"48px 24px", maxWidth:1080, margin:"0 auto" }} id="agents">
      <div style={{ textAlign:"center", marginBottom:28 }}>
        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.accent, textTransform:"uppercase", letterSpacing:"0.15em", marginBottom:6 }}>StreamMind</div>
        <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:"clamp(24px,4vw,36px)", fontWeight:700, color:T.text, letterSpacing:"-0.03em", margin:"0 0 8px" }}>21 AI Agents · 4 Flagships</h2>
        <p style={{ fontFamily:"'Inter',sans-serif", fontSize:14, color:T.textSec, maxWidth:500, margin:"0 auto 18px" }}>
          trigger → data ingestion → LLM reasoning → structured output → action
        </p>
        <div style={{ maxWidth:340, margin:"0 auto 18px" }}>
          <div style={{ display:"flex", justifyContent:"space-between", fontSize:12, fontFamily:"'Inter',sans-serif", color:T.textMuted, marginBottom:5 }}>
            <span><span style={{ color:T.mint, fontWeight:600 }}>{shipped}</span> shipped</span>
            <span>{pct}%</span>
          </div>
          <div style={{ height:5, borderRadius:3, background:T.border }}>
            <div style={{ height:5, borderRadius:3, width:`${pct}%`, background:`linear-gradient(90deg, ${T.mint}, ${T.accent})` }} />
          </div>
        </div>
        <div style={{ display:"flex", justifyContent:"center", gap:6, flexWrap:"wrap" }}>
          {[{ id:"all", label:`All ${total}` }, ...Object.entries(DOMAIN_COLORS).map(([k]) => ({ id:k, label:`${DOMAIN_LABELS[k]} (${AGENTS.filter(a=>a.domain===k).length})` }))].map(f => (
            <button key={f.id} onClick={() => { setFilter(f.id); setOpen(null); }}
              style={{ padding:"6px 14px", fontSize:12, fontWeight:filter===f.id?600:400, color:filter===f.id?T.text:T.textSec, background:filter===f.id?T.elevated:T.surface, border:`1px solid ${filter===f.id?T.borderLight:T.border}`, borderRadius:100, cursor:"pointer", fontFamily:"'Inter',sans-serif" }}>
              {f.label}
            </button>
          ))}
        </div>
      </div>

      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(285px, 1fr))", gap:10 }}>
        {filtered.map(agent => {
          const dc = DOMAIN_COLORS[agent.domain];
          const isOpen = open === agent.id;
          const isShipped = agent.shipped;
          return (
            <div key={agent.id} onClick={() => setOpen(isOpen ? null : agent.id)}
              style={{
                padding:"16px 18px", borderRadius:12, cursor:"pointer", transition:"all 0.2s",
                background: isOpen ? T.elevated : T.card,
                border: `1px solid ${isShipped ? T.mint+"50" : agent.flagship ? T.coral+"40" : isOpen ? T.borderLight : T.border}`,
                boxShadow: isShipped ? `0 0 16px ${T.mintGlow}` : agent.flagship ? `0 0 12px rgba(244,160,179,0.08)` : "none",
                position:"relative", display:"flex", flexDirection:"column",
              }}>
              {isShipped && <div style={{ position:"absolute", top:-1, right:14, padding:"2px 8px", fontSize:10, fontWeight:700, fontFamily:"'Space Grotesk',sans-serif", color:T.bg, background:T.mint, borderRadius:"0 0 5px 5px", letterSpacing:"0.06em", textTransform:"uppercase" }}>Shipped</div>}
              {agent.flagship && !isShipped && <div style={{ position:"absolute", top:-1, right:14, padding:"2px 8px", fontSize:10, fontWeight:700, fontFamily:"'Space Grotesk',sans-serif", color:T.bg, background:T.coral, borderRadius:"0 0 5px 5px", letterSpacing:"0.06em", textTransform:"uppercase" }}>Flagship</div>}
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:8 }}>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:dc, fontWeight:500 }}>{DOMAIN_LABELS[agent.domain]}</span>
                <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:T.textMuted }}>#{String(agent.id).padStart(2,"0")}</span>
              </div>
              <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:15, fontWeight:600, color:T.text, marginBottom:5 }}>{agent.name}</div>
              <div style={{ fontFamily:"'Inter',sans-serif", fontSize:12, color:T.textSec, lineHeight:1.5, marginBottom:10, flex:1 }}>{agent.desc}</div>
              <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"5px 10px", paddingTop:10, borderTop:`1px solid ${T.border}` }}>
                <Tag label="LLM" value={agent.llm} color={T.accent} />
                <Tag label="RAG" value={agent.rag?"Yes":"No"} color={agent.rag?T.mint:T.textMuted} />
                <Tag label="Frmwk" value={agent.framework} color={T.purple} />
                <Tag label="Evals" value="✓" color={T.amber} />
              </div>
              {isOpen && (
                <div style={{ marginTop:10 }}>
                  <div style={{ marginBottom:8, padding:"8px 12px", background:T.surface, borderRadius:6, border:`1px solid ${T.border}` }}>
                    <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:T.amber, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>Eval Strategy</div>
                    <div style={{ fontFamily:"'Inter',sans-serif", fontSize:12, color:T.textSec, lineHeight:1.5 }}>{agent.evals}</div>
                  </div>
                  <div style={{ padding:"8px 12px", background:T.surface, borderRadius:6, border:`1px solid ${T.border}` }}>
                    <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:T.accent, textTransform:"uppercase", letterSpacing:"0.06em", marginBottom:3 }}>Architecture</div>
                    <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:T.accent, lineHeight:1.6 }}>{agent.stack}</div>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ marginTop:20, padding:"18px", background:T.card, border:`1px solid ${T.border}`, borderRadius:12, textAlign:"center" }}>
        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.text, marginBottom:10 }}>Product Stack</div>
        <div style={{ display:"flex", flexWrap:"wrap", gap:6, justifyContent:"center" }}>
          {STACK.map(t => <span key={t} style={{ padding:"4px 12px", fontSize:11, fontFamily:"'JetBrains Mono',monospace", color:T.textSec, background:T.surface, border:`1px solid ${T.border}`, borderRadius:100 }}>{t}</span>)}
        </div>
      </div>
    </section>
  );
}

function CareerSection() {
  const [expanded, setExpanded] = useState(null);
  return (
    <section style={{ padding:"48px 24px", maxWidth:1080, margin:"0 auto" }} id="career">
      <div style={{ textAlign:"center", marginBottom:24 }}>
        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.purple, textTransform:"uppercase", letterSpacing:"0.15em", marginBottom:6 }}>Career</div>
        <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:"clamp(24px,4vw,36px)", fontWeight:700, color:T.text, letterSpacing:"-0.03em", margin:0 }}>10+ Years Building Products</h2>
      </div>
      <div style={{ display:"grid", gap:6 }}>
        {EXPERIENCE.map((e,i) => {
          const isOpen = expanded === i;
          return (
            <div key={i} onClick={() => setExpanded(isOpen ? null : i)}
              style={{ padding:"14px 20px", background:T.card, border:`1px solid ${isOpen?T.borderLight:T.border}`, borderRadius:10, cursor:"pointer", transition:"all 0.15s" }}>
              <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", flexWrap:"wrap", gap:6 }}>
                <div style={{ flex:1, minWidth:180 }}>
                  <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:2 }}>
                    <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:15, fontWeight:600, color:T.text }}>{e.co}</span>
                    <span style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec }}>{e.role}</span>
                  </div>
                  <span style={{ fontFamily:"'Inter',sans-serif", fontSize:12, color:T.textMuted }}>{e.what}</span>
                </div>
                <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
                  <span style={{ padding:"3px 10px", fontSize:11, fontFamily:"'Inter',sans-serif", fontWeight:600, color:T.mint, background:T.mintGlow, border:`1px solid ${T.mint}30`, borderRadius:100 }}>{e.highlight}</span>
                  <span style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:T.textMuted }}>{e.dates}</span>
                </div>
              </div>
              {isOpen && (
                <div style={{ marginTop:10, paddingTop:10, borderTop:`1px solid ${T.border}` }}>
                  {e.bullets.map((b,j) => (
                    <div key={j} style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec, lineHeight:1.6, padding:"2px 0 2px 14px", position:"relative" }}>
                      <span style={{ position:"absolute", left:0, top:9, width:5, height:5, borderRadius:"50%", background:`${T.accent}60` }} />{b}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(280px, 1fr))", gap:10, marginTop:16 }}>
        <div style={{ padding:"18px 20px", background:T.card, border:`1px solid ${T.border}`, borderRadius:10 }}>
          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.accent, marginBottom:8 }}>Education</div>
          <div style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec, lineHeight:1.9 }}>
            <strong style={{ color:T.text }}>Northwestern Kellogg</strong> — PM Certificate, 2022<br/>
            <strong style={{ color:T.text }}>Cal State Fullerton</strong> — MS, MIS, 2017<br/>
            <strong style={{ color:T.text }}>Mumbai University</strong> — BS, IT, 2013
          </div>
        </div>
        <div style={{ padding:"18px 20px", background:T.card, border:`1px solid ${T.border}`, borderRadius:10 }}>
          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.accent, marginBottom:8 }}>Certifications</div>
          <div style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec, lineHeight:1.9 }}>
            <strong style={{ color:T.text }}>Salesforce</strong> — 6 certs + 13 Superbadges<br/>
            <strong style={{ color:T.text }}>Oracle</strong> — SQL & PL/SQL Associate<br/>
            <strong style={{ color:T.text }}>Agile</strong> — CSPO · CSM · SAFe
          </div>
        </div>
      </div>
    </section>
  );
}

function SalesforceShowcase() {
  const sfBlue = "#00A1E0";
  const initiatives = [
    { title:"V2MOM Application", tagline:"Enterprise Goal-Alignment Platform",
      desc:"Led the V2MOM redesign (V2), Salesforce's enterprise goal-alignment platform used by 70,000+ employees. Defined roadmap for 6+ features including goal cascading, KPI splitting, and team views. Shipped to AppExchange as open-source Salesforce Labs solution.",
      metrics:[{n:"70K+",l:"Employees"},{n:"95%",l:"Alignment"},{n:"10+",l:"Mgmt layers"},{n:"6+",l:"Features"}],
      links:[{label:"AppExchange",url:"https://appexchange.salesforce.com/appxListingDetail?listingId=a0N4V00000GHbotUAD"},{label:"GitHub",url:"https://github.com/SalesforceLabs/MyV2MOM"}] },
    { title:"Insiders Program", tagline:"Candidate-Employee Matching Platform",
      desc:"Launched and scaled the Salesforce Insiders Program, a candidate-employee matching platform embedded in the global interview process. Grew to 300+ volunteers across 19 countries.",
      metrics:[{n:"97%",l:"Offer acceptance"},{n:"2,483",l:"Sessions"},{n:"300+",l:"Volunteers"},{n:"19",l:"Countries"}],
      links:[{label:"Blog",url:"https://www.salesforce.com/blog/insiders-program-salesforce-interview-process/"}] },
    { title:"Camp B-Well", tagline:"Employee Wellness Program",
      desc:"Designed Salesforce's employee wellness program across 5 dimensions: physical, mental, nutrition, workspace, and flexibility. Produced 5+ Trailhead modules with measurement framework.",
      metrics:[{n:"5",l:"Dimensions"},{n:"5+",l:"Trailhead modules"}],
      links:[{label:"Blog",url:"https://www.salesforce.com/blog/small-business/small-business-wellness-program/"},{label:"Trailhead",url:"https://trailhead.salesforce.com/content/learn/trails/camp-pono"}] },
  ];
  return (
    <section style={{ padding:"48px 24px", maxWidth:1080, margin:"0 auto" }} id="salesforce">
      <div style={{ textAlign:"center", marginBottom:28 }}>
        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:sfBlue, textTransform:"uppercase", letterSpacing:"0.15em", marginBottom:6 }}>Deep Dive</div>
        <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:"clamp(24px,4vw,36px)", fontWeight:700, color:T.text, letterSpacing:"-0.03em", margin:"0 0 6px" }}>Salesforce — What I Built</h2>
        <p style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec, margin:0 }}>Product Owner, Employee Success · Feb 2021 – Mar 2023</p>
      </div>
      <div style={{ display:"grid", gap:12 }}>
        {initiatives.map((init, i) => (
          <div key={i} style={{ padding:"20px", background:T.card, border:`1px solid ${T.border}`, borderRadius:12, borderLeft:`3px solid ${sfBlue}` }}>
            <div style={{ display:"flex", justifyContent:"space-between", alignItems:"flex-start", flexWrap:"wrap", gap:8, marginBottom:10 }}>
              <div>
                <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:17, fontWeight:600, color:T.text, marginBottom:2 }}>{init.title}</div>
                <div style={{ fontFamily:"'Inter',sans-serif", fontSize:12, color:sfBlue }}>{init.tagline}</div>
              </div>
              <div style={{ display:"flex", gap:5 }}>
                {init.links.map((link, j) => (
                  <a key={j} href={link.url} target="_blank" rel="noopener noreferrer"
                    style={{ padding:"3px 10px", fontSize:11, fontFamily:"'Inter',sans-serif", fontWeight:500, color:sfBlue, background:`${sfBlue}12`, border:`1px solid ${sfBlue}30`, borderRadius:100, textDecoration:"none" }}
                    onClick={e => e.stopPropagation()}>{link.label} ↗</a>
                ))}
              </div>
            </div>
            <p style={{ fontFamily:"'Inter',sans-serif", fontSize:13, color:T.textSec, lineHeight:1.6, margin:"0 0 14px" }}>{init.desc}</p>
            <div style={{ display:"flex", gap:16, flexWrap:"wrap" }}>
              {init.metrics.map((m, k) => (
                <div key={k} style={{ textAlign:"center", minWidth:70 }}>
                  <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:20, fontWeight:700, color:sfBlue, lineHeight:1 }}>{m.n}</div>
                  <div style={{ fontFamily:"'Inter',sans-serif", fontSize:11, color:T.textMuted, marginTop:2 }}>{m.l}</div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      <div style={{ marginTop:12, padding:"14px 20px", background:T.elevated, border:`1px solid ${T.border}`, borderRadius:10, display:"flex", justifyContent:"center", gap:20, flexWrap:"wrap" }}>
        {[{n:"40%",l:"Adoption increase"},{n:"60K",l:"Users supported"},{n:"6",l:"Salesforce certs"},{n:"13",l:"Superbadges"}].map((s,i) => (
          <div key={i} style={{ textAlign:"center" }}>
            <span style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:16, fontWeight:700, color:T.mint }}>{s.n}</span>
            <span style={{ fontFamily:"'Inter',sans-serif", fontSize:11, color:T.textMuted, marginLeft:5 }}>{s.l}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

function SkillsSection() {
  const categories = {
    "AI & Agents": { items:["Claude API","Claude MCP","CrewAI","Agentic Architecture","Prompt Engineering","AI/ML Requirements"], color:T.accent },
    "Automation": { items:["Make","GitHub Actions","Airtable","Supabase","Notion API","Webhooks","REST APIs","OAuth"], color:T.mint },
    "Deployment": { items:["Streamlit","Vercel","HTML/CSS/JS","React"], color:T.purple },
    "Product": { items:["Data-Driven Decisions","A/B Testing","Digital Commerce","Revenue Optimization","Business Cases"], color:T.amber },
    "Analytics": { items:["SQL","Telemetry","GMV / ARPU / Churn","Experimentation Platforms","Data Analytics"], color:T.coral },
    "Execution": { items:["Agile/Scrum","JIRA","Confluence","Figma","Productboard","Backlog Prioritization"], color:T.textSec },
  };
  return (
    <section style={{ padding:"48px 24px", maxWidth:1080, margin:"0 auto" }} id="skills">
      <div style={{ textAlign:"center", marginBottom:24 }}>
        <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color:T.amber, textTransform:"uppercase", letterSpacing:"0.15em", marginBottom:6 }}>Toolkit</div>
        <h2 style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:"clamp(24px,4vw,36px)", fontWeight:700, color:T.text, letterSpacing:"-0.03em", margin:0 }}>Skills & Proficiency</h2>
      </div>
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fill, minmax(280px, 1fr))", gap:10 }}>
        {Object.entries(categories).map(([cat, { items, color }]) => (
          <div key={cat} style={{ padding:"16px 18px", background:T.card, border:`1px solid ${T.border}`, borderRadius:10 }}>
            <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:13, fontWeight:600, color, marginBottom:10, display:"flex", alignItems:"center", gap:6 }}>
              <span style={{ width:7, height:7, borderRadius:"50%", background:color }} />{cat}
            </div>
            <div style={{ display:"flex", flexWrap:"wrap", gap:5 }}>
              {items.map(s => <span key={s} style={{ padding:"3px 10px", fontSize:11, fontFamily:"'JetBrains Mono',monospace", color:T.textSec, background:T.surface, border:`1px solid ${T.border}`, borderRadius:100 }}>{s}</span>)}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function ChatPanel({ onClose }) {
  const [messages, setMessages] = useState([
    { role:"assistant", content:"Hey! I'm Shreya's AI — ask me anything about her experience, agents, skills, or background.\n\nTry: \"What has she shipped?\" or \"Tell me about her Salesforce work.\"" }
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const ref = useRef(null);
  useEffect(() => { ref.current?.scrollIntoView({ behavior:"smooth" }); }, [messages, loading]);
  const send = async () => {
    if (!input.trim() || loading) return;
    const newMsgs = [...messages, { role:"user", content:input.trim() }];
    setMessages(newMsgs); setInput(""); setLoading(true);
    try {
      const chatUrl = window.location.hostname === 'localhost' || window.location.hostname.includes('vercel')
        ? '/api/chat' : 'https://api.anthropic.com/v1/messages';
      const r = await fetch(chatUrl, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body:JSON.stringify({ model:"claude-sonnet-4-6", max_tokens:1000, system:SHREYA_CONTEXT, messages:newMsgs.map(m=>({role:m.role,content:m.content})) })
      });
      const d = await r.json();
      setMessages(p => [...p, { role:"assistant", content:d.content?.map(c=>c.text||"").join("")||"Couldn't process that." }]);
    } catch(e) { setMessages(p => [...p, { role:"assistant", content:"Something went wrong. Try again." }]); }
    setLoading(false);
  };
  return (
    <div style={{ position:"fixed", bottom:72, right:20, width:"min(380px,calc(100vw - 40px))", height:"min(480px,70vh)", background:T.card, border:`1px solid ${T.borderLight}`, borderRadius:16, display:"flex", flexDirection:"column", zIndex:200, boxShadow:`0 8px 40px rgba(0,0,0,0.5), 0 0 40px ${T.glow}` }}>
      <div style={{ padding:"12px 18px", borderBottom:`1px solid ${T.border}`, display:"flex", justifyContent:"space-between", alignItems:"center" }}>
        <div>
          <div style={{ fontFamily:"'Space Grotesk',sans-serif", fontSize:14, fontWeight:600, color:T.text }}>Ask Shreya's AI</div>
          <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:10, color:T.textMuted }}>powered by claude</div>
        </div>
        <button onClick={onClose} style={{ background:"none", border:"none", color:T.textMuted, fontSize:16, cursor:"pointer", padding:4 }}>✕</button>
      </div>
      <div style={{ flex:1, overflowY:"auto", padding:"12px 16px" }}>
        {messages.map((m,i) => (
          <div key={i} style={{ marginBottom:8, display:"flex", justifyContent:m.role==="user"?"flex-end":"flex-start" }}>
            <div style={{ maxWidth:"85%", padding:"8px 12px", fontSize:13, fontFamily:"'Inter',sans-serif", lineHeight:1.6, whiteSpace:"pre-wrap",
              borderRadius:m.role==="user"?"10px 10px 3px 10px":"10px 10px 10px 3px",
              background:m.role==="user"?`${T.accent}18`:T.surface,
              border:`1px solid ${m.role==="user"?`${T.accent}30`:T.border}`, color:T.textSec,
            }}>{m.content}</div>
          </div>
        ))}
        {loading && <div style={{ marginBottom:8 }}><div style={{ display:"inline-block", padding:"8px 12px", borderRadius:"10px 10px 10px 3px", background:T.surface, border:`1px solid ${T.border}`, fontFamily:"'JetBrains Mono',monospace", fontSize:12, color:T.textMuted }}>thinking...</div></div>}
        <div ref={ref} />
      </div>
      <div style={{ padding:"10px 14px", borderTop:`1px solid ${T.border}`, display:"flex", gap:8 }}>
        <input value={input} onChange={e=>setInput(e.target.value)} onKeyDown={e=>e.key==="Enter"&&send()}
          placeholder="Ask about experience, agents, skills..."
          style={{ flex:1, padding:"8px 12px", fontSize:13, fontFamily:"'Inter',sans-serif", background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, color:T.text, outline:"none" }} />
        <button onClick={send} disabled={loading}
          style={{ padding:"8px 16px", fontSize:13, fontWeight:600, background:T.accent, color:"#fff", border:"none", borderRadius:8, opacity:loading?0.5:1, fontFamily:"'Inter',sans-serif" }}>Send</button>
      </div>
    </div>
  );
}

export default function Portfolio() {
  const [chatOpen, setChatOpen] = useState(false);
  return (
    <div style={{ minHeight:"100vh", background:T.bg, color:T.text }}>
      <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
      <Hero />
      <div style={{ maxWidth:100, margin:"0 auto", height:1, background:`linear-gradient(90deg, transparent, ${T.accent}, transparent)` }} />
      <StreamMindSection />
      <div style={{ maxWidth:100, margin:"0 auto", height:1, background:`linear-gradient(90deg, transparent, ${T.purple}, transparent)` }} />
      <CareerSection />
      <div style={{ maxWidth:100, margin:"0 auto", height:1, background:`linear-gradient(90deg, transparent, #00A1E0, transparent)` }} />
      <SalesforceShowcase />
      <div style={{ maxWidth:100, margin:"0 auto", height:1, background:`linear-gradient(90deg, transparent, ${T.amber}, transparent)` }} />
      <SkillsSection />
      <footer style={{ padding:"28px 24px", textAlign:"center", borderTop:`1px solid ${T.border}` }}>
        <div style={{ fontFamily:"'JetBrains Mono',monospace", fontSize:11, color:T.textMuted }}>shreya patel · 2026 · built with claude</div>
      </footer>
      {!chatOpen && (
        <button onClick={() => setChatOpen(true)}
          style={{ position:"fixed", bottom:20, right:20, width:52, height:52, borderRadius:"50%", background:T.accent, border:"none", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center", fontSize:22, boxShadow:`0 4px 20px ${T.glow}`, zIndex:100 }}>💬</button>
      )}
      {chatOpen && <ChatPanel onClose={() => setChatOpen(false)} />}
    </div>
  );
}
