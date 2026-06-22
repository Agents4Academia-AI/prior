import { useCallback, useEffect, useState } from "react";
import { ReactFlowProvider } from "@xyflow/react";
import { api } from "./lib/api";
import type {
  Summary,
  Paper,
  GlobalGraph,
  PaperGraph,
  ContributionDetail,
  ClaimNode,
} from "./lib/types";
import Sidebar from "./components/Sidebar";
import GlobalView from "./components/GlobalView";
import LocalView from "./components/LocalView";
import Legend from "./components/Legend";
import DetailsPanel from "./components/DetailsPanel";
import AskPanel from "./components/AskPanel";

type Mode = "global" | "local";
type Tab = "details" | "ask";

export default function App() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("global");
  const [tab, setTab] = useState<Tab>("details");

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

  // Boot: summary, papers, global graph.
  useEffect(() => {
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
    setTab("details");
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

  const onLocalNode = useCallback(
    (id: string) => {
      setSelectedNodeId(id);
      setContribution(null);
      setContribError(null);
      setTab("details");
      const node = paperGraph?.nodes.find((n) => n.id === id) ?? null;
      setSelectedClaim(node);
    },
    [paperGraph],
  );

  return (
    <div className="app">
      <Sidebar
        summary={summary}
        papers={papers}
        selectedPaperId={selectedPaperId}
        onSelectPaper={openPaper}
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
            />
            <Legend mode="global" />
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
            className={tab === "ask" ? "on" : ""}
            onClick={() => setTab("ask")}
          >
            Ask
          </button>
        </div>
        <div className="pane">
          {tab === "details" ? (
            <DetailsPanel
              contribution={contribution}
              contribLoading={contribLoading}
              contribError={contribError}
              claim={selectedClaim}
              paperGraph={paperGraph}
            />
          ) : (
            <AskPanel />
          )}
        </div>
      </div>
    </div>
  );
}
