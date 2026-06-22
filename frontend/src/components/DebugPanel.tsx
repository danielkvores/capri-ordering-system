import { DebugPayload, SessionState } from "../api";

type Props = {
  debug: DebugPayload | null;
  session: SessionState | null;
};

export function DebugPanel({ debug, session }: Props) {
  const payload = {
    last_user_input: session?.last_user_message ?? null,
    llm_raw_response: debug?.llm_raw ?? null,
    parsed_action_json: debug?.parsed_action ?? null,
    validation_result: debug?.validation ?? null,
    backend_applied_changes: debug?.applied_changes ?? [],
    latency_ms: debug?.latency_ms ?? null,
    errors: debug?.errors ?? [],
  };

  return (
    <section className="panel debug-panel">
      <div className="panel-header">
        <h2>Debug JSON</h2>
      </div>
      <pre>{JSON.stringify(payload, null, 2)}</pre>
    </section>
  );
}
