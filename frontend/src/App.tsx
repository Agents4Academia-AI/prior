import { useCallback, useEffect, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { api, type WhoAmI } from "./lib/api";
import type {
  Summary,
  Paper,
  GlobalGraph,
  GlobalEdge,
  PaperGraph,
  ClaimEdge,
  ContributionDetail,
  ClaimNode,
} from "./lib/types";
import Sidebar from "./components/Sidebar";
import GlobalView from "./components/GlobalView";
import LocalView from "./components/LocalView";
import EvalView from "./components/EvalView";
import Legend from "./components/Legend";
import DetailsPanel, { type SelectedEdge } from "./components/DetailsPanel";
import AskPanel from "./components/AskPanel";
import AnnotatePanel, { type AnnotationTarget } from "./components/AnnotatePanel";

type Mode = "global" | "local" | "eval";
type Tab = "details" | "ask" | "annotate";

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("global");
  const [tab, setTab] = useState<Tab>("details");
  const [relFilter, setRelFilter] = useState<string | null>(null);

  const [globalGraph, setGlobalGraph] = useState<GlobalGraph | null>(null);

  const [selectedPaperId, setSelectedPaperId] = useState<string | null>(null);
  const [paperGraph, setPaperGraph] = useState<PaperGraph | null>(null);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperError, setPaperError] = useState<string | null>(null);

  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);
  const [contribution, setContribution] = useState<ContributionDetail | null>(
    null,
  );
  const [contribLoading, setContribLoading] = useState(false);
  const [contribError, setContribError] = useState<string | null>(null);
  const [selectedClaim, setSelectedClaim] = useState<ClaimNode | null>(null);
  const [selectedEdge, setSelectedEdge] = useState<SelectedEdge | null>(null);
  const [who, setWho] = useState<WhoAmI | null>(null);

  const refreshWho = useCallback(() => {
    api.whoami().then(setWho).catch(() => setWho(null));
  }, []);

  // Re-fetch the current graph so freshly-saved annotation tallies show up.
  const onAnnotated = useCallback(() => {
    refreshWho();
    api.globalGraph().then(setGlobalGraph).catch(() => {});
    if (selectedPaperId)
      api.paperGraph(selectedPaperId).then(setPaperGraph).catch(() => {});
  }, [refreshWho, selectedPaperId]);

  // After a paper is ingested, refresh the corpus + graph.
  const onIngested = useCallback(() => {
    api.summary().then(setSummary).catch(() => {});
    api.papers().then(setPapers).catch(() => {});
    api.globalGraph().then(setGlobalGraph).catch(() => {});
  }, []);

  // Boot: summary, papers, global graph, identity.
  useEffect(() => {
    refreshWho();
    (async () => {
      try {
        const [s, p, g] = await Promise.all([
          api.summary(),
          api.papers(),
          api.globalGraph(),
        ]);
        setSummary(s);
        setPapers(p);
        setGlobalGraph(g);
      } catch (e) {
        setBootError(e instanceof Error ? e.message : String(e));
      }
    })();
  }, []);

  const openPaper = useCallback(async (paper: Paper) => {
    setSelectedPaperId(paper.id);
    setMode("local");
    setSelectedNodeId(null);
    setSelectedClaim(null);
    setSelectedEdge(null);
    setContribution(null);
    setPaperLoading(true);
    setPaperError(null);
    try {
      setPaperGraph(await api.paperGraph(paper.id));
    } catch (e) {
      setPaperError(e instanceof Error ? e.message : String(e));
      setPaperGraph(null);
    } finally {
      setPaperLoading(false);
    }
  }, []);

  const onGlobalNode = useCallback(async (id: string) => {
    setSelectedNodeId(id);
    setSelectedClaim(null);
    setSelectedEdge(null);
    setTab((t) => (t === "ask" ? "details" : t));
    setContribLoading(true);
    setContribError(null);
    setContribution(null);
    try {
      setContribution(await api.contribution(id));
    } catch (e) {
      setContribError(e instanceof Error ? e.message : String(e));
    } finally {
      setContribLoading(false);
    }
  }, []);

  const onGlobalEdge = useCallback((e: GlobalEdge) => {
    setContribution(null);
    setSelectedClaim(null);
    setSelectedNodeId(null);
    setTab((t) => (t === "ask" ? "details" : t));
    setSelectedEdge({
      source: e.source, target: e.target, relation: e.relation,
      provenance: e.provenance, evidence: e.evidence,
    });
  }, []);

  const onLocalEdge = useCallback((e: ClaimEdge) => {
    setContribution(null);
    setSelectedClaim(null);
    setSelectedNodeId(null);
    setTab((t) => (t === "ask" ? "details" : t));
    setSelectedEdge({
      source: e.source, target: e.target, relation: e.relation, evidence: e.evidence,
    });
  }, []);

  const onLocalNode = useCallback(
    (id: string) => {
      setSelectedNodeId(id);
      setContribution(null);
      setContribError(null);
      setSelectedEdge(null);
      setTab((t) => (t === "ask" ? "details" : t));
      const node = paperGraph?.nodes.find((n) => n.id === id) ?? null;
      setSelectedClaim(node);
    },
    [paperGraph],
  );

  // Normalize the current selection into an annotation target (for the Annotate tab).
  const annotationTarget: AnnotationTarget | null = selectedEdge
    ? {
        kind: "edge",
        key: `${selectedEdge.source}|${selectedEdge.relation.toUpperCase()}|${selectedEdge.target}`,
        heading: `Relation: ${selectedEdge.relation}`,
        fields: [
          { label: "from", value: selectedEdge.source },
          { label: "to", value: selectedEdge.target },
          ...(selectedEdge.evidence ? [{ label: "why", value: selectedEdge.evidence }] : []),
        ],
      }
    : selectedClaim
    ? {
        kind: "claim",
        key: selectedClaim.id,
        heading: `Claim (${selectedClaim.claim_type})`,
        fields: [
          { label: "claim", value: selectedClaim.label },
          ...(selectedClaim.evidence ? [{ label: "evidence", value: selectedClaim.evidence }] : []),
        ],
        source: paperGraph?.paper.cite,
      }
    : contribution
    ? {
        kind: "contribution",
        key: contribution.id,
        heading: "Contribution",
        fields: [
          { label: "problem", value: contribution.problem },
          { label: "method", value: contribution.method },
          { label: "result", value: contribution.result },
        ],
        source: papers.find((p) => p.id === contribution.paper_id)?.cite,
      }
    : null;

  return (
    <div className="app">
      <Sidebar
        summary={summary}
        papers={papers}
        selectedPaperId={selectedPaperId}
        onSelectPaper={openPaper}
        who={who}
        onIdentityChange={refreshWho}
        onIngested={onIngested}
      />

      <div className="panel canvas">
        <div className="toolbar">
          <div className="toggle">
            <button
              className={mode === "global" ? "on" : ""}
              onClick={() => setMode("global")}
            >
              Global
            </button>
            <button
              className={mode === "local" ? "on" : ""}
              onClick={() => setMode("local")}
              disabled={!paperGraph}
              title={
                paperGraph ? "" : "Select a paper to view its claim graph"
              }
            >
              Local
            </button>
            <button
              className={mode === "eval" ? "on" : ""}
              onClick={() => setMode("eval")}
            >
              Eval
            </button>
          </div>
          {mode === "global" && (
            <div className="canvas-banner">
              <b>Contribution graph.</b> Solid edges are citation-backed; dashed
              edges are uncited parallel work inferred from text.
            </div>
          )}
          {mode === "local" && paperGraph && (
            <div className="canvas-banner">
              <b>{paperGraph.paper.cite}</b> — claim graph
            </div>
          )}
        </div>

        {bootError && (
          <div className="center-fill">
            <div className="err">Could not reach the backend: {bootError}</div>
            <div className="muted">Is the API running at {api.base}?</div>
          </div>
        )}

        {!bootError && mode === "global" && globalGraph && (
          <ReactFlowProvider>
            <GlobalView
              graph={globalGraph}
              selectedId={selectedNodeId}
              onSelectNode={onGlobalNode}
              onSelectEdge={onGlobalEdge}
              activeRelation={relFilter}
            />
            <Legend
              mode="global"
              activeRelation={relFilter}
              onPickRelation={setRelFilter}
            />
          </ReactFlowProvider>
        )}

        {!bootError && mode === "global" && !globalGraph && (
          <div className="center-fill">
            <span className="spinner" />
            Loading global graph…
          </div>
        )}

        {!bootError && mode === "local" && (
          <>
            {paperLoading && (
              <div className="center-fill">
                <span className="spinner" />
                Loading claim graph…
              </div>
            )}
            {paperError && (
              <div className="center-fill">
                <div className="err">{paperError}</div>
              </div>
            )}
            {!paperLoading && !paperError && paperGraph && (
              <ReactFlowProvider>
                <LocalView
                  graph={paperGraph}
                  selectedId={selectedNodeId}
                  onSelectNode={onLocalNode}
                  onSelectEdge={onLocalEdge}
                />
                <Legend mode="local" />
              </ReactFlowProvider>
            )}
            {!paperLoading && !paperError && !paperGraph && (
              <div className="center-fill">
                Select a paper from the left to view its claim graph.
              </div>
            )}
          </>
        )}

        {!bootError && mode === "eval" && <EvalView />}
      </div>

      <div className="panel right">
        <div className="tabs">
          <button
            className={tab === "details" ? "on" : ""}
            onClick={() => setTab("details")}
          >
            Details
          </button>
          <button
            className={tab === "annotate" ? "on" : ""}
            onClick={() => setTab("annotate")}
          >
            Annotate
          </button>
          <button
            className={tab === "ask" ? "on" : ""}
            onClick={() => setTab("ask")}
          >
            Ask
          </button>
        </div>
        <div className="pane">
          {tab === "details" && (
            <DetailsPanel
              contribution={contribution}
              contribLoading={contribLoading}
              contribError={contribError}
              claim={selectedClaim}
              paperGraph={paperGraph}
              edge={selectedEdge}
            />
          )}
          {tab === "annotate" && (
            <AnnotatePanel
              target={annotationTarget}
              signedIn={!!who?.signed_in}
              onAnnotated={onAnnotated}
            />
          )}
          {tab === "ask" && <AskPanel />}
        </div>
      </div>
    </div>
  );
}
