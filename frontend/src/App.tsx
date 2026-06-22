import { useEffect, useState } from "react";
import {
  ChatMessage,
  DebugPayload,
  MenuPayload,
  SessionState,
  confirmOrder,
  createSession,
  getMenu,
  resetSession,
  sendMessage,
} from "./api";
import { ConversationPanel } from "./components/ConversationPanel";
import { DebugPanel } from "./components/DebugPanel";
import { InputPanel } from "./components/InputPanel";
import { MenuPanel } from "./components/MenuPanel";
import { OrderPanel } from "./components/OrderPanel";

export default function App() {
  const [session, setSession] = useState<SessionState | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [menu, setMenu] = useState<MenuPayload | null>(null);
  const [debug, setDebug] = useState<DebugPayload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void startSession();
    getMenu().then(setMenu).catch((err) => setError(err.message));
  }, []);

  async function startSession() {
    setLoading(true);
    setError(null);
    try {
      const response = await createSession();
      setSession(response.session);
      setMessages(response.messages);
      setDebug(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not start session.");
    } finally {
      setLoading(false);
    }
  }

  async function handleReset() {
    if (!session) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await resetSession(session.session_id);
      setSession(response.session);
      setMessages(response.messages);
      setDebug(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not reset session.");
    } finally {
      setLoading(false);
    }
  }

  async function handleSend(text: string) {
    if (!session) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await sendMessage(session.session_id, text);
      setSession(response.session);
      setMessages(response.messages);
      setDebug(response.debug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not send message.");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!session) {
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await confirmOrder(session.session_id);
      setSession(response.session);
      setMessages(response.messages);
      setDebug(response.debug);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not confirm order.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>Restaurant Voice Ordering Prototype</h1>
          <p>Milestone 1 text-only local ordering loop</p>
        </div>
        <div className="header-actions">
          <span className="status-pill">{session?.status ?? "starting"}</span>
          <button type="button" onClick={startSession} disabled={loading}>
            Start New Session
          </button>
          <button type="button" onClick={handleReset} disabled={!session || loading}>
            Reset Session
          </button>
        </div>
      </header>

      {error ? <div className="error-banner">{error}</div> : null}

      <section className="main-grid">
        <div className="left-column">
          <InputPanel onSend={handleSend} loading={loading || !session} />
          <ConversationPanel messages={messages} />
        </div>
        <OrderPanel session={session} onConfirm={handleConfirm} loading={loading} />
        <div className="right-column">
          <DebugPanel debug={debug} session={session} />
          <MenuPanel menu={menu} />
        </div>
      </section>
    </main>
  );
}
