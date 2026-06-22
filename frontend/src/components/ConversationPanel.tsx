import { ChatMessage } from "../api";

type Props = {
  messages: ChatMessage[];
};

export function ConversationPanel({ messages }: Props) {
  return (
    <section className="panel conversation-panel">
      <div className="panel-header">
        <h2>Conversation</h2>
      </div>
      <div className="messages">
        {messages.map((message, index) => (
          <article className={`message ${message.role}`} key={`${message.created_at}-${index}`}>
            <span>{message.role === "user" ? "Customer" : "Assistant"}</span>
            <p>{message.text}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
