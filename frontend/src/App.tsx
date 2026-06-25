import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, type WhoAmI, type CollectionInfo } from "./lib/api";
import type { Summary, Paper, PaperGraph, ClaimNode } from "./lib/types";
import NavRail from "./components/NavRail";
import PapersView from "./components/PapersView";
import PaperLink from "./components/PaperLink";
import MethodsView from "./components/MethodsView";
import EvalView from "./components/EvalView";
import AskPanel from "./components/AskPanel";
import ClaimGraph, { type ClaimEdgePick } from "./components/ClaimGraph";
import AnnotatePanel, { type AnnotationTarget } from "./components/AnnotatePanel";

type Mode = "graph" | "local" | "eval" | "papers" | "report";
type Overlay = "none" | "annotate" | "ask";
const DOCK_MIN = 300, DOCK_MAX = 760;

type SelNode = {
  level: "contribs" | "papers";
  node: { id: string; kind?: string; stmt?: string; quote?: string; cite?: string; title?: string };
};
type SelEdge = { source: string; target: string; rel: string; ev?: string; tier?: string };

export default function App() {
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [collection, setCollection] = useState<string>("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("graph");
  const [overlay, setOverlay] = useState<Overlay>("none");
  const [railOpen, setRailOpen] = useState(true);
  const [dockWidth, setDockWidth] = useState(400);
  const [resizing, setResizing] = useState(false);
  const [sel, setSel] = useState<SelNode | null>(null);
  const [selEdge, setSelEdge] = useState<SelEdge | null>(null);

  const [localPaper, setLocalPaper] = useState<PaperGraph | null>(null);
  const [localLoading, setLocalLoading] = useState(false);
  const [selClaim, setSelClaim] = useState<ClaimNode | null>(null);
  const [selClaimEdge, setSelClaimEdge] = useState<ClaimEdgePick | null>(null);
  const [who, setWho] = useState<WhoAmI | null>(null);

  const refreshWho = useCallback(() => {
    api.whoami().then(setWho).catch(() => setWho(null));
  }, []);

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
      } catch (e) {
        setBootError(e instanceof Error ? e.message : String(e));
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const h = (e: MessageEvent) => {
      if (e.data?.type === "prior-select") {
        setSel({ level: e.data.level, node: e.data.node }); setSelEdge(null);
      } else if (e.data?.type === "prior-select-edge") {
        setSelEdge({ source: e.data.source, target: e.data.target, rel: e.data.rel,
                     ev: e.data.ev, tier: e.data.tier });
        setSel(null);
      }
    };
    window.addEventListener("message", h);
    return () => window.removeEventListener("message", h);
  }, []);

  const switchCollection = useCallback((coll: string) => {
    if (coll === collection) return;
    setCollection(coll); setSel(null); setMode("graph"); setLocalPaper(null);
    api.summary(coll).then(setSummary).catch(() => {});
    api.papers(coll).then(setPapers).catch(() => {});
  }, [collection]);

  const onAnnotated = useCallback(() => { refreshWho(); }, [refreshWho]);

  const navigate = useCallback((m: "graph" | "papers" | "eval" | "report") => { setMode(m); }, []);

  const draggingRef = useRef(false);
  const startResize = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    draggingRef.current = true;
    setResizing(true);              // overlay captures events over the graph iframe
    const onMove = (ev: MouseEvent) => {
      if (!draggingRef.current) return;
      const w = window.innerWidth - ev.clientX;
      setDockWidth(Math.min(DOCK_MAX, Math.max(DOCK_MIN, w)));
    };
    const onUp = () => {
      draggingRef.current = false;
      setResizing(false);
      document.removeEventListener("mousemove", onMove);
      document.removeEventListener("mouseup", onUp);
    };
    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
  }, []);

  const openLocal = useCallback(() => {
    if (!sel) return;
    const paperId = sel.node.id.split("::")[0];
    setLocalPaper(null); setSelClaim(null); setSelClaimEdge(null); setLocalLoading(true); setMode("local");
    api.paperGraph(paperId).then(setLocalPaper).catch(() => setLocalPaper(null))
      .finally(() => setLocalLoading(false));
  }, [sel]);

  const exitLocal = useCallback(() => {
    setMode("graph"); setLocalPaper(null); setSelClaim(null); setSelClaimEdge(null);
  }, []);

  const onIngested = useCallback(() => {
    api.summary(collection).then(setSummary).catch(() => {});
    api.papers(collection).then(setPapers).catch(() => {});
    const f = document.getElementById("viewer") as HTMLIFrameElement | null;
    if (f) f.src = f.src; // eslint-disable-line no-self-assign
  }, [collection]);

  // contribution annotation (atlas mode) / claim annotation (local mode)
  const annotationTarget: AnnotationTarget | null = useMemo(() => {
    if (mode === "local") {
      if (selClaimEdge) {
        return {
          kind: "edge",
          key: `${selClaimEdge.source}|${selClaimEdge.relation.toUpperCase()}|${selClaimEdge.target}`,
          heading: `Claim relation: ${selClaimEdge.relation}`,
          fields: [
            { label: "from", value: selClaimEdge.source },
            { label: "to", value: selClaimEdge.target },
          ],
          source: localPaper?.paper.cite,
        };
      }
      if (!selClaim) return null;
      return {
        kind: "claim", key: selClaim.id,
        heading: `Claim (${selClaim.claim_type})`,
        fields: [
          { label: "claim", value: selClaim.label },
          ...(selClaim.evidence ? [{ label: "evidence", value: selClaim.evidence }] : []),
        ],
        source: localPaper?.paper.cite,
      };
    }
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
    if (sel?.level === "contribs") {
      const n = sel.node;
      return {
        kind: "contribution", key: n.id,
        heading: `Contribution (${n.kind || "contribution"})`,
        fields: [
          { label: "statement", value: n.stmt || "" },
          ...(n.quote ? [{ label: "quote", value: n.quote }] : []),
        ],
        source: n.cite,
      };
    }
    return null;
  }, [mode, sel, selEdge, selClaim, selClaimEdge, localPaper]);

  const viewerSrc = collection
    ? `/viewer.html?api=${encodeURIComponent(api.base)}&collection=${encodeURIComponent(collection)}`
    : "";

  const dockOpen = overlay !== "none";
  const MODE_TITLE: Record<string, string> = { graph: "Atlas", eval: "Evaluation", papers: "", report: "" };

  return (
    <div className="app">
      {resizing && <div className="resize-overlay" />}
      <NavRail
        mode={mode}
        onNavigate={navigate}
        open={railOpen}
        onToggle={() => setRailOpen((o) => !o)}
        collections={collections}
        collection={collection}
        onSwitchCollection={switchCollection}
        who={who}
        onIdentityChange={refreshWho}
      />

      <div className="panel canvas">
        <div className="canvas-bar">
          <div className="bar-left">
            {mode === "local" ? (
              <>
                <button className="btn-ghost sm" onClick={exitLocal}>← Atlas</button>
                {localPaper ? (
                  <PaperLink paper={localPaper.paper} className="bar-title">
                    {localPaper.paper.cite ?? "claim graph"}
                  </PaperLink>
                ) : <span className="bar-title">claim graph</span>}
              </>
            ) : (
              <span className="bar-title">{MODE_TITLE[mode] ?? ""}</span>
            )}
          </div>
          <div className="bar-right">
            {mode === "graph" && sel && (
              <button className="btn-ghost sm" onClick={openLocal}>Claims ↳</button>
            )}
            {mode === "graph" && (selEdge || sel?.level === "contribs") && (
              <button className="btn-primary sm" onClick={() => setOverlay("annotate")}>
                ✎ Annotate {selEdge ? "edge" : ""}
              </button>
            )}
            <button className="btn-ghost sm" onClick={() => setOverlay("ask")}>Ask</button>
          </div>
        </div>

        <div className="canvas-body">
          {bootError && (
            <div className="center-fill">
              <div className="err">Could not reach the backend: {bootError}</div>
              <div className="muted">Is the API running at {api.base}?</div>
            </div>
          )}

          {!bootError && mode === "papers" && (
            <PapersView summary={summary} papers={papers} collection={collection} onIngested={onIngested} />
          )}

          {!bootError && mode === "report" && <MethodsView />}

          {!bootError && mode === "graph" && viewerSrc && (
            <iframe id="viewer" key={collection} className="viewer-frame" title="Prior atlas" src={viewerSrc} />
          )}

          {!bootError && mode === "local" && (
            <div className="local-split">
              <div className="local-graph">
                {localLoading ? (
                  <div className="center-fill"><span className="spinner" /> Loading claims…</div>
                ) : localPaper ? (
                  <ClaimGraph
                    graph={localPaper}
                    highlightContrib={sel?.level === "contribs" ? sel.node.id : null}
                    selectedId={selClaim?.id ?? null}
                    onSelectClaim={(c) => { setSelClaim(c); setSelClaimEdge(null); }}
                    onSelectEdge={(e) => { setSelClaimEdge(e); setSelClaim(null); }}
                  />
                ) : (
                  <div className="center-fill"><div className="err">Could not load claims.</div></div>
                )}
              </div>
              <div className="local-side">
                <div className="ls-head">Annotate {selClaimEdge ? "relation" : "claim"}</div>
                <AnnotatePanel target={annotationTarget} signedIn={!!who?.signed_in} onAnnotated={onAnnotated} />
              </div>
            </div>
          )}

          {!bootError && mode === "eval" && <EvalView />}
        </div>
      </div>

      {dockOpen && (
        <>
          <div className="resizer" onMouseDown={startResize} title="Drag to resize" />
          <div className="panel dock" style={{ width: dockWidth }}>
            <div className="dock-head">
              <h3>{overlay === "annotate" ? "Annotate" : "Ask the graph"}</h3>
              <button className="modal-x" onClick={() => setOverlay("none")}>×</button>
            </div>
            <div className="dock-body">
              {overlay === "annotate"
                ? <AnnotatePanel target={annotationTarget} signedIn={!!who?.signed_in} onAnnotated={onAnnotated} />
                : <AskPanel />}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
