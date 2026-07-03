import { useEffect, useState } from "react";
import { api, type EvalResults, type CalibDim } from "../lib/api";

const PCT = (v: number | null | undefined) => (v == null ? "-" : `${Math.round(v * 100)}%`);
const NUM = (v: number | null | undefined) => (v == null ? "-" : v.toFixed(2));

// ── references ──────────────────────────────────────────────────────────────────
type Ref = { id: string; cite: string; title: string; url: string };
const REFS: Ref[] = [
  { id: "guo2017", cite: "Guo et al., 2017", title: "On Calibration of Modern Neural Networks", url: "https://arxiv.org/abs/1706.04599" },
  { id: "zheng2023", cite: "Zheng et al., 2023", title: "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena", url: "https://arxiv.org/abs/2306.05685" },
  { id: "panick2024", cite: "Panickssery et al., 2024", title: "LLM Evaluators Recognize and Favor Their Own Generations", url: "https://arxiv.org/abs/2404.13076" },
  { id: "xiong2024", cite: "Xiong et al., 2024", title: "Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation", url: "https://arxiv.org/abs/2306.13063" },
  { id: "wadden2020", cite: "Wadden et al., 2020", title: "Fact or Fiction: Verifying Scientific Claims (SciFact)", url: "https://arxiv.org/abs/2004.14974" },
  { id: "cohan2019", cite: "Cohan et al., 2019", title: "Structural Scaffolds for Citation Intent Classification (SciCite)", url: "https://arxiv.org/abs/1904.01608" },
  { id: "lala2023", cite: "Lála et al., 2023", title: "PaperQA: Retrieval-Augmented Generative Agent for Scientific Research", url: "https://arxiv.org/abs/2312.07559" },
  { id: "skarlinski2024", cite: "Skarlinski et al., 2024", title: "Language Agents Achieve Superhuman Synthesis of Scientific Knowledge (PaperQA2)", url: "https://arxiv.org/abs/2409.13740" },
  { id: "lu2024", cite: "Lu et al., 2024", title: "The AI Scientist: Towards Fully Automated, Open-Ended Scientific Discovery", url: "https://arxiv.org/abs/2408.06292" },
  { id: "auer2018", cite: "Auer et al., 2018", title: "Open Research Knowledge Graph", url: "https://arxiv.org/abs/1901.10816" },
  { id: "ammar2018", cite: "Ammar et al., 2018", title: "Construction of the Literature Graph in Semantic Scholar", url: "https://aclanthology.org/N18-3011/" },
];
const R: Record<string, Ref> = Object.fromEntries(REFS.map((r) => [r.id, r]));
function Cite({ id }: { id: string }) {
  const r = R[id];
  if (!r) return null;
  return <a className="mv-cite" href={r.url} target="_blank" rel="noopener noreferrer" title={r.title}>({r.cite})</a>;
}

function Badge({ children, tone }: { children: React.ReactNode; tone?: string }) {
  return <span className={`mv-badge${tone ? ` ${tone}` : ""}`}>{children}</span>;
}
function Section({ n, title, children }: { n: string; title: string; children: React.ReactNode }) {
  return (
    <section className="mv-section">
      <h3><span className="mv-secn">{n}</span> {title}</h3>
      {children}
    </section>
  );
}

// horizontal pipeline diagram
function PipelineDiagram() {
  const stages = [
    { x: 8, label: "Ingest", sub: "OpenAlex + arXiv", tone: "#8a8a93" },
    { x: 132, label: "Reader", sub: "Sonnet", tone: "#c96442" },
    { x: 256, label: "Cartographer", sub: "Sonnet", tone: "#c96442" },
    { x: 380, label: "Consensus", sub: "trust + tier", tone: "#8a8a93" },
    { x: 504, label: "Self-eval", sub: "judge", tone: "#c96442" },
    { x: 628, label: "Navigator", sub: "Opus", tone: "#7a52a0" },
  ];
  const W = 740, BW = 104, BH = 46, y = 16;
  return (
    <svg viewBox={`0 0 ${W} 92`} className="mv-diagram" role="img" aria-label="pipeline diagram">
      <defs>
        <marker id="mvarr" markerWidth="8" markerHeight="8" refX="6" refY="3" orient="auto">
          <path d="M0,0 L6,3 L0,6 Z" fill="#9aa0b0" />
        </marker>
      </defs>
      {stages.map((s, i) => (
        <g key={s.label}>
          {i < stages.length - 1 && (
            <line x1={s.x + BW} y1={y + BH / 2} x2={stages[i + 1].x} y2={y + BH / 2}
                  stroke="#9aa0b0" strokeWidth={1.4} markerEnd="url(#mvarr)" />
          )}
          <rect x={s.x} y={y} width={BW} height={BH} rx={9} fill="var(--bg-elev)" stroke={s.tone} strokeWidth={1.4} />
          <text x={s.x + BW / 2} y={y + 19} textAnchor="middle" fontSize={13} fontWeight={600} fill="var(--text)">{s.label}</text>
          <text x={s.x + BW / 2} y={y + 34} textAnchor="middle" fontSize={10.5} fill={s.tone}>{s.sub}</text>
        </g>
      ))}
      <text x={8} y={86} fontSize={10.5} fill="var(--text-faint)">
        Per paper: contributions + claims with verbatim evidence. Across papers: typed, trust-scored relations. Opus answers; Sonnet does the volume.
      </text>
    </svg>
  );
}

export default function MethodsView() {
  const [d, setD] = useState<EvalResults | null>(null);
  useEffect(() => { api.eval().then(setD).catch(() => {}); }, []);

  const sum = d?.summary;
  const dim = (k: string) => d?.scorecard.dimensions.find((x) => x.kind === k);
  const cov = (k: string, total?: number) => {
    const n = dim(k)?.self_eval.n ?? 0;
    return total ? `${n} / ${total} (${Math.round((100 * n) / total)}%)` : `${n}`;
  };
  const cal = (kind: string, signal: string): CalibDim | undefined =>
    d?.calibration?.dimensions.find((x) => x.kind === kind && x.signal === signal);

  return (
    <div className="methods paper">
      <header className="mv-title">
        <h1>Prior: a self-auditing, two-level knowledge graph of the scientific literature</h1>
        <div className="mv-authors">System report, generated live from the running instance · collection core-v0.2</div>
      </header>

      <div className="mv-abstract">
        <b>Abstract.</b> Prior reads a corpus of papers and builds a grounded knowledge graph at two
        levels: within each paper it extracts research contributions and atomic claims, each tied to a
        verbatim quote, and across papers it infers typed relations (builds_on, refines, supports,
        contradicts) using a "citations propose, text disposes" procedure. Relations are scored for
        trust by a consensus step that combines the model's stated confidence with embedding
        similarity. A retrieval based Navigator answers research questions with an explicit verdict
        (established, contested, emerging, not_found) cited to primary claims. Distinctively, the
        system audits its own extraction with an LLM judge and reports calibration: whether the stored
        confidence and trust scores actually predict faithfulness, measured by AUC-ROC and Expected
        Calibration Error. On the current corpus of {sum?.papers ?? "the"} papers we find that the
        consensus trust ranks faithful relations better than raw confidence yet remains overconfident,
        and that per-claim confidence is near chance. We discuss the central threat to validity, a
        judge that shares a model family with the extractor, and outline cheap, independent evaluations
        that address it.
      </div>

      {sum && (
        <div className="mv-kpis">
          <div className="mv-kpi"><b>{sum.papers}</b><span>papers</span></div>
          <div className="mv-kpi"><b>{sum.contributions}</b><span>contributions</span></div>
          <div className="mv-kpi"><b>{sum.claims}</b><span>claims</span></div>
          <div className="mv-kpi"><b>{sum.global_edges}</b><span>relations</span></div>
          {sum.local_edges > 0 && <div className="mv-kpi"><b>{sum.local_edges}</b><span>local edges</span></div>}
        </div>
      )}

      <Section n="1" title="Introduction">
        <p>
          Deciding whether a research idea has already been tried, and what the weight of evidence is,
          means reading many papers and tracking how their claims relate: which corroborate, which
          conflict, which build on which. Doing this by hand does not scale, and asking a language
          model to summarize a topic from memory produces fluent but ungrounded answers that cannot be
          checked. Prior takes a middle path. It converts a topic into a queryable graph whose every
          node is anchored to a verbatim span of a real paper, and it answers questions only from that
          graph, returning an honest "not found" when the evidence is absent.
        </p>
        <p>
          Two design commitments shape the system. First, <b>grounding</b>: every contribution and
          claim keeps the quote it came from, so a human can verify it and the Navigator can cite it.
          Second, <b>self-auditing</b>: because any automated extractor makes mistakes, Prior grades
          its own output with an LLM judge and, crucially, reports how trustworthy its confidence
          signals are rather than presenting them as fact. The contributions of this report are (i) a
          description of the end-to-end pipeline and its design choices, (ii) the self-evaluation
          protocol, and (iii) a calibration analysis of the confidence and trust scores against the
          judge, with an honest account of the main bias in that analysis.
        </p>
      </Section>

      <Section n="2" title="Related work">
        <p>
          <b>Grounded scientific QA and research agents.</b> Prior is closest in spirit to
          retrieval-augmented scientific agents such as PaperQA and PaperQA2 <Cite id="lala2023" />{" "}
          <Cite id="skarlinski2024" />, which answer questions over primary sources with low citation
          hallucination. It differs in output: rather than prose or a full generated paper as in
          autonomous pipelines like The AI Scientist <Cite id="lu2024" />, Prior emits a structured,
          inspectable claim graph plus a verdict, and it is deliberately conservative, surfacing
          contradictions and gaps instead of generating new findings.
        </p>
        <p>
          <b>Claim and citation mining.</b> The claim layer and the typed relations draw on scientific
          claim verification, where evidence must support or refute a stated claim <Cite id="wadden2020" />,
          and on citation-intent classification, which labels why one work cites another{" "}
          <Cite id="cohan2019" />. Prior fuses these: it mines the claims itself and then scores
          cross-paper agreement at scale, turning contradiction detection into a many-to-many problem
          handled by the trust score.
        </p>
        <p>
          <b>Scholarly knowledge graphs.</b> The contribution schema echoes the Open Research Knowledge
          Graph, which relates a research problem to method and result <Cite id="auer2018" />, and the
          paper/citation layer resembles the Semantic Scholar literature graph <Cite id="ammar2018" />.
          Prior adds an LLM-built, evidence-grounded claim and relation layer on top, produced from
          primary text rather than templates or crowdsourcing.
        </p>
        <p>
          <b>LLM-as-judge and calibration.</b> Using an LLM to grade outputs is now standard and agrees
          well with humans, but it carries a documented self-enhancement bias in which a model favors
          its own generations <Cite id="zheng2023" /> <Cite id="panick2024" />. This is exactly why
          Prior's self-eval needs an independent judge. Separately, model confidence is known to be
          poorly calibrated: modern networks are overconfident <Cite id="guo2017" />, and LLM verbalized
          confidence in particular clusters near the top of the scale and is miscalibrated{" "}
          <Cite id="xiong2024" />. Prior therefore treats its own confidence as an untrustworthy signal
          to be measured, not reported as truth.
        </p>
      </Section>

      <Section n="3" title="System overview">
        <p className="muted">High volume extraction runs on Sonnet; Opus is reserved for the user facing answer.</p>
        <PipelineDiagram />
        <p>
          The graph has three tiers. The <b>global</b> tier links contributions across papers with
          typed relations. The <b>local</b> tier links claims within a paper (entails, supports,
          contradicts, depends_on), capturing internal logic. A <b>meta</b> tier records provenance:
          a claim is stated in a paper, supports a contribution, and a paper cites another. All of it
          lives in Neo4j and is read live, so the views reflect ongoing ingestion without a rebuild.
        </p>
      </Section>

      <Section n="4" title="Method">
        <div className="mv-stages">
          {[
            ["Ingest", "", "Papers are pulled from OpenAlex (relevance search, reviews and abstract-less works filtered out) and topped up from arXiv. Citation edges can be walked backward to reach an idea's origins that keyword search misses. Open-access full text is resolved through a cascade: arXiv HTML, then the OpenAlex open-access PDF, then Unpaywall by DOI, then sanctioned publisher text-mining APIs (Elsevier, Springer, Wiley), with an optional, policy-limited institutional path. Cross-source duplicates are merged on a normalized-title key. Defaults: 25 papers, 48k characters of body text per paper (a 70 percent head plus 30 percent tail window, since intro and conclusion carry most contributions)."],
            ["Reader: contributions and claims", "claude-sonnet-4-6", "One forced-tool call per paper returns three things and nothing else. Contributions (typically one to three) each carry a one-sentence statement, a kind (empirical_finding, framework, method, benchmark, dataset, model, analysis, resource, system, other), a verbatim quote, and a confidence in [0,1]. Claims (three to eight) are atomic, pronoun-resolved assertions with a claim_type, an evidence span, a confidence, and a pointer to the contribution they support. Local edges relate claims within the paper. The prompt forbids invention: every item must be grounded in the supplied text. Papers run six at a time."],
            ["Cartographer: cross-paper relations", "claude-sonnet-4-6", "Candidate pairs come from two sources unioned together: the papers a contribution's paper cites, and its BM25 nearest contributions from other papers (six by default). The model then labels each ordered pair with a relation (builds_on, refines, contradicts, contrast, supports, mentions), a one-line reason, and a confidence, and is told most pairs are unrelated and to be conservative. Each edge is stamped with provenance: both if the pair was citation and text, otherwise text or citation. This is the 'citations propose, text disposes' design: citations suggest where to look, the text decides what holds."],
            ["Consensus: trust and tier", "embeddings + label", "Each relation is scored by combining the model's confidence c with the cosine similarity s of the two contributions' embeddings (mxbai-embed-large, 1024-dim, served on CPU). Single-model: trust = 0.7·c + 0.3·s, and a tier of triple, double, or single by how many of the two signals are strong (c ≥ 0.65, s ≥ 0.5). An optional Opus-arbiter mode labels each pair with both Sonnet and Opus and uses trust = 0.4·c_opus + 0.4·c_sonnet(if they agree) + 0.2·s. The graph's 'min trust' knob filters on this score."],
            ["Index, embed, cluster", "", "Contributions and claims are embedded and stored with a cosine vector index in Neo4j for nearest-neighbour retrieval. For the atlas view, contributions are grouped by greedy-modularity community detection over the relation graph (up to nine clusters of size eight or more), labelled by keyword voting, and laid out deterministically on a golden-angle spiral so the picture is stable across reloads."],
            ["Navigator: answer a question", "claude-opus-4-8", "For a question, the top claims are retrieved (BM25 or vector ANN), and the model returns a verdict (established, contested, emerging, not_found) with supporting and contradicting evidence cited by id, plus the closest work and the gap when nothing matches. A parallel 'has this been solved' mode works over contributions and their relation neighbourhoods. This is the only Opus stage: low volume, high stakes, and strictly grounded in retrieved evidence."],
          ].map(([name, model, text]) => (
            <div className="mv-stage" key={name as string}>
              <div className="mv-stage-body">
                <div className="mv-stage-head">
                  <h4>{name}</h4>
                  {model && <Badge tone={(model as string).includes("opus") ? "opus" : (model as string).includes("sonnet") ? "sonnet" : ""}>{model}</Badge>}
                </div>
                <div className="mv-stage-text">{text}</div>
              </div>
            </div>
          ))}
        </div>
        <p className="muted" style={{ marginTop: 10 }}>
          All model calls go through one interface with a forced tool, so structured output is always
          valid JSON. The backend is pluggable: the metered Anthropic API, or the credit-free Claude
          Code session (used here), or a local open-weight server over an OpenAI-compatible endpoint.
        </p>
      </Section>

      <Section n="5" title="Evaluation methodology">
        <p>
          The judge is one Sonnet call per item, forced through a <code>judge</code> tool that returns{" "}
          <Badge>verdict: correct | incorrect | unsure</Badge> and a short reason. The three task
          prompts ask, respectively, whether a contribution is a faithful and supported representation
          of its quote, whether a relation genuinely holds in its stated direction, and whether a
          claim's evidence actually supports it. Runs are incremental: already-judged items are
          skipped, six judged in parallel.
        </p>
        <p>
          We then ask whether a stored score predicts the judge's verdict. We report two complementary
          metrics. <b>AUC-ROC</b> is threshold-free and measures discrimination: the probability that a
          randomly chosen faithful item is scored higher than a randomly chosen unfaithful one, where
          0.5 is chance. <b>Expected Calibration Error</b> bins items by score and averages the gap
          between mean score and empirical accuracy in each bin <Cite id="guo2017" />; the reliability
          diagram plots that bin-wise relationship against the diagonal. AUC can be high while ECE is
          poor: a score can rank well yet sit far from the accuracy it implies.
        </p>
        <h4 style={{ margin: "14px 0 6px" }}>Coverage</h4>
        <table className="mv-table">
          <thead><tr><th>Dimension</th><th>Judged</th><th>Self-eval correct</th></tr></thead>
          <tbody>
            <tr><td>Contributions</td><td>{cov("contribution", sum?.contributions)}</td><td>{PCT(dim("contribution")?.self_eval.correct)}</td></tr>
            <tr><td>Relations (edges)</td><td>{cov("edge", sum?.global_edges)}</td><td>{PCT(dim("edge")?.self_eval.correct)}</td></tr>
            <tr><td>Claims</td><td>{cov("claim", sum?.claims)}</td><td>{PCT(dim("claim")?.self_eval.correct)}</td></tr>
          </tbody>
        </table>
        <p className="muted" style={{ marginTop: 6 }}>
          Coverage is partial: items added after the last run stay unjudged. Re-run{" "}
          <code>prior selfeval --collection &lt;name&gt;</code> to finish.
        </p>
      </Section>

      <Section n="6" title="Results">
        <p>
          AUC-ROC, ECE, and base correctness for each stored score against the judge (full reliability
          and threshold curves are on the Eval tab):
        </p>
        <table className="mv-table">
          <thead><tr><th>Score</th><th>n</th><th>AUC</th><th>ECE</th><th>base correct</th></tr></thead>
          <tbody>
            {[["contribution", "confidence"], ["claim", "confidence"], ["edge", "confidence"], ["edge", "trust"]].map(([k, s]) => {
              const c = cal(k, s);
              return (
                <tr key={`${k}/${s}`}>
                  <td>{k} · {s}</td><td>{c?.n ?? "-"}</td><td>{NUM(c?.auc)}</td><td>{NUM(c?.ece)}</td><td>{PCT(c?.accuracy)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p style={{ marginTop: 8 }}>
          Three findings stand out. <b>Claim confidence is near chance</b> as a faithfulness signal: it
          saturates near 1.0, so it cannot separate good claims from bad, consistent with reports that
          LLM verbalized confidence is overconfident and uninformative <Cite id="xiong2024" />.{" "}
          <b>Consensus trust beats raw confidence</b> for edges (higher AUC), which is why the graph
          knob filters on trust, but it remains <b>overconfident</b> (high ECE): a trust value is a
          useful ranking, not an accuracy, so a threshold of 0.7 does not mean 70 percent faithful.
          These are live numbers and will shift as more items are judged.
        </p>
      </Section>

      <Section n="7" title="Limitations">
        <ul className="mv-list">
          <li><b>The judge shares a model family with the extractor.</b> The self-eval ran on Sonnet, the same family that produced much of the extraction. LLM judges exhibit self-enhancement bias, favoring their own generations <Cite id="zheng2023" /> <Cite id="panick2024" />, so the reported correctness is an optimistic upper bound. An independent judge is the fix, not an optional extra.</li>
          <li><b>Provenance is not recorded.</b> The extraction model is not stored per node, and core-v0.2 was loaded from a prebuilt bundle whose contributions lack a confidence field, which is why some calibration cells are empty. Stamping each node with its producing model and run is needed to interpret these numbers cleanly.</li>
          <li><b>Ground truth is the judge, not humans.</b> Human labels are sparse, so calibration is a self-consistency audit rather than external validation. A small stratified human sample would anchor it.</li>
          <li><b>Confidence is verbalized, not probabilistic.</b> The scores come from the model stating a number, which is known to be miscalibrated <Cite id="xiong2024" />; recalibration (for example temperature scaling or isotonic regression against judged labels) is not yet applied.</li>
        </ul>
      </Section>

      <Section n="8" title="Future work">
        <ul className="mv-list">
          <li><b>Multi-judge panel.</b> Run the audit with Opus (credit-free via the Claude session) and a local open-weight model, each writing under its own label. The plumbing exists: <code>prior selfeval --model … --judge …</code>. Disagreement across judges flags exactly the items a human should review, and cross-judge agreement replaces sparse human labels as the reliability signal.</li>
          <li><b>Recalibration.</b> Fit a monotone map from trust to empirical faithfulness on judged data so the knob reads as accuracy.</li>
          <li><b>Cheap deterministic checks.</b> Token overlap between a claim and its evidence span (no LLM); temporal direction sanity on builds_on and refines edges; near-duplicate detection over the existing embeddings.</li>
          <li><b>Provenance and re-audit.</b> Record the producing model per node and re-run the judge with a different model to quantify the self-enhancement gap directly.</li>
        </ul>
      </Section>

      <Section n="R" title="References">
        <ol className="mv-refs">
          {REFS.map((r) => (
            <li key={r.id}><a href={r.url} target="_blank" rel="noopener noreferrer">{r.cite}</a>. {r.title}.</li>
          ))}
        </ol>
      </Section>
    </div>
  );
}
