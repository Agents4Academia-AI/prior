import { useEffect, useRef, useState } from "react";
import { api, type IngestJob } from "../lib/api";

type Mode = "arxiv" | "pdf_url" | "pdf_upload";

const STEPS = ["queued", "fetching", "extracting", "relating", "done"];

export default function AddPaper({ onIngested, collection }: { onIngested: () => void; collection: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="addpaper">
      <button className="add-trigger" onClick={() => setOpen(true)}>
        + Add paper
      </button>
      {open && <AddPaperModal onClose={() => setOpen(false)} onIngested={onIngested} collection={collection} />}
    </div>
  );
}

function AddPaperModal({
  onClose,
  onIngested,
  collection,
}: {
  onClose: () => void;
  onIngested: () => void;
  collection: string;
}) {
  const [mode, setMode] = useState<Mode>("arxiv");
  const [value, setValue] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [job, setJob] = useState<IngestJob | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const poll = useRef<number | null>(null);

  useEffect(() => () => { if (poll.current) window.clearInterval(poll.current); }, []);

  const submit = async (force = false) => {
    setErr(null); setBusy(true); setJob(null);
    try {
      const { job_id } = await api.ingest(mode, mode === "pdf_upload" ? "" : value, file, force, collection);
      poll.current = window.setInterval(async () => {
        try {
          const st = await api.ingestStatus(job_id);
          setJob(st);
          if (st.status === "done" || st.status === "failed" || st.status === "duplicate") {
            window.clearInterval(poll.current!);
            setBusy(false);
            if (st.status === "done") onIngested();
          }
        } catch {/* keep polling */}
      }, 1500);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
      setBusy(false);
    }
  };

  const stepIdx = job ? STEPS.indexOf(job.status === "relating" ? "relating" : job.status) : -1;
  const done = job?.status === "done";
  const failed = job?.status === "failed";
  const dup = job?.status === "duplicate";
  const versionDup = dup && job?.duplicate_of?.kind === "version";

  return (
    <div className="modal-backdrop" onClick={busy ? undefined : onClose}>
      <div className="modal wide" onClick={(e) => e.stopPropagation()}>
        <div className="modal-head">
          <h3>Add a paper</h3>
          <button className="modal-x" onClick={onClose}>×</button>
        </div>

        {!job && (
          <>
            <div className="seg">
              {([["arxiv", "arXiv"], ["pdf_url", "PDF URL"], ["pdf_upload", "Upload PDF"]] as [Mode, string][]).map(
                ([m, l]) => (
                  <button key={m} className={`seg-btn ${mode === m ? "on" : ""}`}
                          onClick={() => setMode(m)}>{l}</button>
                ))}
            </div>
            <div className="add-input">
              {mode === "arxiv" && (
                <input autoFocus placeholder="arXiv id or URL (e.g. 2106.09685)"
                       value={value} onChange={(e) => setValue(e.target.value)} />
              )}
              {mode === "pdf_url" && (
                <input autoFocus placeholder="https://…/paper.pdf"
                       value={value} onChange={(e) => setValue(e.target.value)} />
              )}
              {mode === "pdf_upload" && (
                <input type="file" accept="application/pdf"
                       onChange={(e) => setFile(e.target.files?.[0] ?? null)} />
              )}
            </div>
            <p className="modal-sub">
              The paper is fetched, its contributions &amp; claims are extracted, and it’s
              merged into the graph in the background — this can take a minute or two.
            </p>
            {err && <div className="err">{err}</div>}
            <div className="modal-actions">
              <button className="btn-ghost" onClick={onClose}>Cancel</button>
              <button className="btn-primary" onClick={() => submit()}
                      disabled={busy || (mode === "pdf_upload" ? !file : !value.trim())}>
                Add paper
              </button>
            </div>
          </>
        )}

        {job && dup && (
          <div className="ingest-progress">
            {job.title && <div className="ip-title">{job.title}</div>}
            <div className="dup-note">{job.message}</div>
            <div className="modal-actions">
              <button className="btn-ghost" onClick={onClose}>Close</button>
              {versionDup && (
                <button className="btn-primary" onClick={() => submit(true)} disabled={busy}>
                  Add anyway
                </button>
              )}
            </div>
          </div>
        )}

        {job && !dup && (
          <div className="ingest-progress">
            {job.title && <div className="ip-title">{job.title}</div>}
            <ol className="steps">
              {STEPS.map((s, i) => (
                <li key={s} className={
                  failed ? (i <= stepIdx ? "err-step" : "")
                  : i < stepIdx || done ? "done-step"
                  : i === stepIdx ? "active-step" : ""}>
                  {s === "done" ? "added to graph" : s}
                </li>
              ))}
            </ol>
            <div className={`ip-msg ${failed ? "err" : ""}`}>
              {failed ? job.error : done
                ? `Added: ${job.result.contribs ?? 0} contributions, ${job.result.claims ?? 0} claims, ${job.result.edges ?? 0} new edges.`
                : job.message}
            </div>
            <div className="modal-actions">
              <button className="btn-primary" onClick={onClose}>
                {done || failed ? "Close" : "Run in background"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
