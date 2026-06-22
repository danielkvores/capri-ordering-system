import { FormEvent, useState } from "react";

type Props = {
  loading: boolean;
  onSend: (text: string) => void;
};

export function InputPanel({ loading, onSend }: Props) {
  const [text, setText] = useState("");

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value) {
      return;
    }
    onSend(value);
    setText("");
  }

  return (
    <section className="panel input-panel">
      <div className="panel-header">
        <h2>Customer Input</h2>
      </div>
      <form onSubmit={handleSubmit}>
        <textarea
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder="Hungarian customer text, e.g. Szia, kérek két Margherita pizzát elvitelre."
          disabled={loading}
        />
        <div className="input-actions">
          <button type="submit" disabled={loading || !text.trim()}>
            Send Text
          </button>
        </div>
      </form>
    </section>
  );
}
