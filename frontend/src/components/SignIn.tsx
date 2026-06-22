import { useState } from "react";
import { api, getIdentity, setIdentity, type WhoAmI } from "../lib/api";

export default function SignIn({
  who,
  onChange,
}: {
  who: WhoAmI | null;
  onChange: () => void;
}) {
  const existing = getIdentity();
  const [user, setUser] = useState(existing?.user ?? "");
  const [token, setToken] = useState(existing?.token ?? "");
  const [err, setErr] = useState<string | null>(null);

  const signIn = async () => {
    setErr(null);
    setIdentity({ user: user.trim(), token });
    try {
      const w = await api.whoami();
      if (!w.signed_in) {
        setErr("Invalid username or token.");
        setIdentity(null);
      }
      onChange();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  };
  const signOut = () => {
    setIdentity(null);
    setUser("");
    setToken("");
    onChange();
  };

  if (who?.signed_in) {
    return (
      <div className="signin in">
        <span className="who-name">
          {who.user}
          {who.is_admin && <span className="badge admin">admin</span>}
          {who.open_mode && <span className="badge open">open</span>}
        </span>
        <span className="who-count">{who.annotated ?? 0} annotated</span>
        <button className="link" onClick={signOut}>
          sign out
        </button>
      </div>
    );
  }

  return (
    <div className="signin">
      <input
        placeholder="name"
        value={user}
        onChange={(e) => setUser(e.target.value)}
      />
      <input
        placeholder="token"
        type="password"
        value={token}
        onChange={(e) => setToken(e.target.value)}
      />
      <button onClick={signIn} disabled={!user.trim()}>
        sign in
      </button>
      {err && <div className="err">{err}</div>}
    </div>
  );
}
