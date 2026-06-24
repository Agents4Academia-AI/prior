import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type WhoAmI, type RenderPayload, type RContrib, type CollectionInfo } from "./lib/api";
import type { Summary, Paper } from "./lib/types";
import Sidebar from "./components/Sidebar";
import GraphD3, { type EdgePick } from "./components/GraphD3";
import ClusterLegend from "./components/ClusterLegend";
import EvalView from "./components/EvalView";
import ContribDetails from "./components/ContribDetails";
import AskPanel from "./components/AskPanel";
import AnnotatePanel, { type AnnotationTarget } from "./components/AnnotatePanel";

type Mode = "graph" | "eval";
type Tab = "details" | "annotate" | "ask";

const NODE_CAPS = [150, 300, 600, 0]; // 0 = all

export default function App() {
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [collection, setCollection] = useState<string>("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [payload, setPayload] = useState<RenderPayload | null>(null);
  const [bootError, setBootError] = useState<string | null>(null);
  const [loadingGraph, setLoadingGraph] = useState(false);

  const [mode, setMode] = useState<Mode>("graph");
  const [tab, setTab] = useState<Tab>("details");
  const [maxNodes, setMaxNodes] = useState<number>(300);
  const [minTrust, setMinTrust] = useState<number>(0);
  const [focusComm, setFocusComm] = useState<number | null>(null);

  const [selContrib, setSelContrib] = useState<RContrib | null>(null);
  const [selEdge, setSelEdge] = useState<EdgePick | null>(null);
  const [who, setWho] = useState<WhoAmI | null>(null);

  const refreshWho = useCallback(() => {
    api.whoami().then(setWho).catch(() => setWho(null));
  }, []);

  const loadGraph = useCallback((coll: string, max: number, trust: number) => {
    setLoadingGraph(true);
    return api.renderGlobal(coll, { maxNodes: max, minTrust: trust })
      .then(setPayload).catch((e) => setBootError(String(e)))
      .finally(() => setLoadingGraph(false));
  }, []);

  // boot: collections → default → summary/papers/graph
  useEffect(() => {
    refreshWho();
    (async () => {
      try {
        const cs = await api.collections();
        setCollections(cs.collections);
        const coll = cs.collections.some((c) => c.name === cs.default)
          ? cs.default : (cs.collections[0]?.name ?? cs.default);
        setCollection(coll);
        const [s, p] = await Promise.all([api.summary(coll), api.papers(coll)]);
        setSummary(s); setPapers(p);
        await loadGraph(coll, 300, 0);
      } catch (e) {
        setBootError(e instanceof Error ? e.message : String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const switchCollection = useCallback((coll: string) => {
    if (coll === collection) return;
    setCollection(coll);
    setSelContrib(null); setSelEdge(null); setFocusComm(null);
    api.summary(coll).then(setSummary).catch(() => {});
    api.papers(coll).then(setPapers).catch(() => {});
    loadGraph(coll, maxNodes, minTrust);
  }, [collection, maxNodes, minTrust, loadGraph]);

  const setCap = useCallback((max: number) => {
    setMaxNodes(max); loadGraph(collection, max, minTrust);
  }, [collection, minTrust, loadGraph]);
  const setTrust = useCallback((t: number) => {
    setMinTrust(t); loadGraph(collection, maxNodes, t);
  }, [collection, maxNodes, loadGraph]);

  const onSelectNode = useCallback((id: string | null) => {
    setSelEdge(null);
    setSelContrib(id ? payload?.contribs.find((c) => c.id === id) ?? null : null);
    if (id) setTab((t) => (t === "ask" ? "details" : t));
  }, [payload]);

  const onSelectEdge = useCallback((e: EdgePick) => {
    setSelContrib(null); setSelEdge(e);
    setTab((t) => (t === "ask" ? "details" : t));
  }, []);

  const onAnnotated = useCallback(() => { refreshWho(); }, [refreshWho]);

  const onIngested = useCallback(() => {
    // ingestion re-clusters server-side; refresh corpus + graph
    api.summary(collection).then(setSummary).catch(() => {});
    api.papers(collection).then(setPapers).catch(() => {});
    loadGraph(collection, maxNodes, minTrust);
  }, [collection, maxNodes, minTrust, loadGraph]);

  const annotationTarget: AnnotationTarget | null = useMemo(() => {
    if (selEdge) {
      return {
        kind: "edge",
        key: `${selEdge.source}|${selEdge.rel.toUpperCase()}|${selEdge.target}`,
        heading: `Relation: ${selEdge.rel}`,
        fields: [
          { label: "from", value: selEdge.source },
          { label: "to", value: selEdge.target },
          ...(selEdge.ev ? [{ label: "why", value: selEdge.ev }] : []),
        ],
      };
    }
    if (selContrib) {
      return {
        kind: "contribution",
        key: selContrib.id,
        heading: `Contribution (${selContrib.kind})`,
        fields: [
          { label: "statement", value: selContrib.stmt },
          ...(selContrib.quote ? [{ label: "quote", value: selContrib.quote }] : []),
        ],
        source: selContrib.cite,
      };
    }
    return null;
  }, [selContrib, selEdge]);

  const selectedId = selContrib?.id ?? null;

  return (
    <div className="app">
      <Sidebar
        summary={summary}
        papers={papers}
        collections={collections}
        collection={collection}
        onSwitchCollection={switchCollection}
        who={who}
        onIdentityChange={refreshWho}
        onIngested={onIngested}
      />

      <div className="panel canvas">
        <div className="toolbar">
          <div className="toggle">
            <button className={mode === "graph" ? "on" : ""} onClick={() => setMode("graph")}>Graph</button>
            <button className={mode === "eval" ? "on" : ""} onClick={() => setMode("eval")}>Eval</button>
          </div>
          {mode === "graph" && payload && (
            <div className="canvas-banner">
              <b>{payload.topic || collection}</b> — {payload.n_contribs} contributions
              {payload.capped && <> · showing densest {payload.n_contribs} of {payload.total_contribs}</>}
            </div>
          )}
          {mode === "graph" && (
            <div className="constraints">
              <label>nodes
                <select value={maxNodes} onChange={(e) => setCap(Number(e.target.value))}>
                  {NODE_CAPS.map((c) => <option key={c} value={c}>{c === 0 ? "all" : c}</option>)}
                </select>
              </label>
              <label>min&nbsp;trust&nbsp;{minTrust.toFixed(1)}
                <input type="range" min={0} max={0.9} step={0.1} value={minTrust}
                       onChange={(e) => setTrust(Number(e.target.value))} />
              </label>
            </div>
          )}
        </div>

        {bootError && (
          <div className="center-fill">
            <div className="err">Could not reach the backend: {bootError}</div>
            <div className="muted">Is the API running at {api.base}?</div>
          </div>
        )}

        {!bootError && mode === "graph" && payload && (
          <>
            <GraphD3
              key={`${collection}:${maxNodes}:${minTrust}`}
              payload={payload}
              selectedId={selectedId}
              focusComm={focusComm}
              onSelectNode={onSelectNode}
              onSelectEdge={onSelectEdge}
            />
            <ClusterLegend
              legend={payload.legend}
              focusComm={focusComm}
              onPick={(id) => setFocusComm((cur) => (cur === id ? null : id))}
            />
            {loadingGraph && <div className="graph-loading">updating…</div>}
          </>
        )}

        {!bootError && mode === "graph" && !payload && (
          <div className="center-fill"><span className="spinner" />Loading graph…</div>
        )}

        {!bootError && mode === "eval" && <EvalView />}
      </div>

      <div className="panel right">
        <div className="tabs">
          <button className={tab === "details" ? "on" : ""} onClick={() => setTab("details")}>Details</button>
          <button className={tab === "annotate" ? "on" : ""} onClick={() => setTab("annotate")}>Annotate</button>
          <button className={tab === "ask" ? "on" : ""} onClick={() => setTab("ask")}>Ask</button>
        </div>
        <div className="pane">
          {tab === "details" && (
            <ContribDetails contrib={selContrib} edge={selEdge} relColor={payload?.rel ?? {}} />
          )}
          {tab === "annotate" && (
            <AnnotatePanel target={annotationTarget} signedIn={!!who?.signed_in} onAnnotated={onAnnotated} />
          )}
          {tab === "ask" && <AskPanel />}
        </div>
      </div>
    </div>
  );
}
