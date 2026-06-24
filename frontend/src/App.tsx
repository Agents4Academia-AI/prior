import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type WhoAmI, type CollectionInfo } from "./lib/api";
import type { Summary, Paper } from "./lib/types";
import Sidebar from "./components/Sidebar";
import EvalView from "./components/EvalView";
import AskPanel from "./components/AskPanel";
import AnnotatePanel, { type AnnotationTarget } from "./components/AnnotatePanel";

type Mode = "graph" | "eval";

type SelNode = {
  level: "contribs" | "papers";
  node: { id: string; kind?: string; stmt?: string; quote?: string; cite?: string; title?: string };
};

export default function App() {
  const [collections, setCollections] = useState<CollectionInfo[]>([]);
  const [collection, setCollection] = useState<string>("");
  const [summary, setSummary] = useState<Summary | null>(null);
  const [papers, setPapers] = useState<Paper[]>([]);
  const [bootError, setBootError] = useState<string | null>(null);

  const [mode, setMode] = useState<Mode>("graph");
  const [overlay, setOverlay] = useState<"none" | "annotate" | "ask">("none");
  const [sel, setSel] = useState<SelNode | null>(null);
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
      if (e.data?.type === "prior-select") setSel({ level: e.data.level, node: e.data.node });
    };
    window.addEventListener("message", h);
    return () => window.removeEventListener("message", h);
  }, []);

  const switchCollection = useCallback((coll: string) => {
    if (coll === collection) return;
    setCollection(coll); setSel(null);
    api.summary(coll).then(setSummary).catch(() => {});
    api.papers(coll).then(setPapers).catch(() => {});
  }, [collection]);

  const onAnnotated = useCallback(() => { refreshWho(); }, [refreshWho]);

  const onIngested = useCallback(() => {
    api.summary(collection).then(setSummary).catch(() => {});
    api.papers(collection).then(setPapers).catch(() => {});
    const f = document.getElementById("viewer") as HTMLIFrameElement | null;
    if (f) f.src = f.src; // eslint-disable-line no-self-assign
  }, [collection]);

  const annotationTarget: AnnotationTarget | null = useMemo(() => {
    if (!sel || sel.level !== "contribs") return null;
    const n = sel.node;
    return {
      kind: "contribution",
      key: n.id,
      heading: `Contribution (${n.kind || "contribution"})`,
      fields: [
        { label: "statement", value: n.stmt || "" },
        ...(n.quote ? [{ label: "quote", value: n.quote }] : []),
      ],
      source: n.cite,
    };
  }, [sel]);

  const viewerSrc = collection
    ? `/viewer.html?api=${encodeURIComponent(api.base)}&collection=${encodeURIComponent(collection)}`
    : "";

  return (
    <div className="app two-col">
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
        </div>
        {mode === "graph" && (
          <div className="toolbar-right">
            {sel && sel.level === "contribs" && (
              <button className="btn-primary sm" onClick={() => setOverlay("annotate")}>✎ Annotate</button>
            )}
            <button className="btn-ghost sm" onClick={() => setOverlay("ask")}>Ask</button>
          </div>
        )}

        {bootError && (
          <div className="center-fill">
            <div className="err">Could not reach the backend: {bootError}</div>
            <div className="muted">Is the API running at {api.base}?</div>
          </div>
        )}

        {!bootError && mode === "graph" && viewerSrc && (
          <iframe id="viewer" key={collection} className="viewer-frame" title="Prior atlas" src={viewerSrc} />
        )}
        {!bootError && mode === "eval" && <EvalView />}
      </div>

      {overlay !== "none" && (
        <div className="modal-backdrop" onClick={() => setOverlay("none")}>
          <div className="modal side-modal" onClick={(e) => e.stopPropagation()}>
            <div className="modal-head">
              <h3>{overlay === "annotate" ? "Annotate" : "Ask the graph"}</h3>
              <button className="modal-x" onClick={() => setOverlay("none")}>×</button>
            </div>
            {overlay === "annotate" ? (
              <AnnotatePanel target={annotationTarget} signedIn={!!who?.signed_in} onAnnotated={onAnnotated} />
            ) : (
              <AskPanel />
            )}
          </div>
        </div>
      )}
    </div>
  );
}
