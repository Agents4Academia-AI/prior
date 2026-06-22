import { useState } from "react";
import { api, getIdentity, setIdentity, type WhoAmI } from "../lib/api";

export default function SignIn({
  who,
  onChange,
}: {
  who: WhoAmI | null;
  onChange: () => void;
}) {
  const [open, setOpen] = useState(false);

  if (who?.signed_in) {
    return (
      <div className="account in">
        <span className="who-name">{who.user}</span>
        {who.is_admin && <span className="badge admin">admin</span>}
        {who.open_mode && <span className="badge open">open</span>}
        <span className="who-count">{who.annotated ?? 0} annotated</span>
        <button
          className="link"
          onClick={() => {
            setIdentity(null);
            onChange();
          }}
        >
          sign out
        </button>
      </div>
    );
  }

  return (
    <div className="account">
      <button className="signin-trigger" onClick={() => setOpen(true)}>
        Sign in to annotate
      </button>
      {open && (
        <SignInModal
          onClose={() => setOpen(false)}
          onChange={onChange}
        />
      )}
    </div>
  );
}

function SignInModal({
  onClose,
  onChange,
}: {
  onClose: () => void;
  onChange: () => void;
}) {
  const existing = getIdentity();
  const [user, setUser] = useState(existing?.user ?? "");
  const [password, setPassword] = useState(existing?.password ?? "");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    setIdentity({ user: user.trim(), password });
    try {
      const w = await api.whoami();
      if (!w.signed_in) {
        setErr("Invalid username or password.");
        setIdentity(null);
        return;
      }
      onChange();
      onClose();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <form
        className="modal"
        onClick={(e) => e.stopPropagation()}
        onSubmit={submit}
      >
        <div className="modal-head">
          <h3>Sign in</h3>
          <button type="button" className="modal-x" onClick={onClose}>
            ×
          </button>
        </div>
        <p className="modal-sub">
          Annotate to help verify the graph. Your annotations are private to you.
        </p>
        <label>
          Username
          <input
            autoFocus
            value={user}
            onChange={(e) => setUser(e.target.value)}
            placeholder="your name"
          />
        </label>
        <label>
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            placeholder="password (blank if open demo)"
          />
        </label>
        {err && <div className="err">{err}</div>}
        <div className="modal-actions">
          <button type="button" className="btn-ghost" onClick={onClose}>
            Cancel
          </button>
          <button type="submit" className="btn-primary" disabled={!user.trim() || busy}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </div>
  );
}
