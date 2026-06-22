import { SessionState } from "../api";

type Props = {
  session: SessionState | null;
  loading: boolean;
  onConfirm: () => void;
};

export function OrderPanel({ session, loading, onConfirm }: Props) {
  if (!session) {
    return (
      <section className="panel order-panel">
        <div className="panel-header">
          <h2>Current Order</h2>
        </div>
        <p>No active session.</p>
      </section>
    );
  }

  const canConfirm = session.status === "awaiting_final_confirmation" && session.missing_fields.length === 0;

  return (
    <section className="panel order-panel">
      <div className="panel-header">
        <h2>Current Order</h2>
      </div>
      <dl className="order-facts">
        <div>
          <dt>Status</dt>
          <dd>{session.status}</dd>
        </div>
        <div>
          <dt>Customer</dt>
          <dd>{session.customer.name ?? "Missing"}</dd>
        </div>
        <div>
          <dt>Phone</dt>
          <dd>{session.customer.phone ?? "Missing"}</dd>
        </div>
        <div>
          <dt>Profile</dt>
          <dd>{session.customer.profile_found ? "Found" : session.customer.profile_unresolved ? "Unresolved" : "Not checked"}</dd>
        </div>
        <div>
          <dt>Fulfilment</dt>
          <dd>{session.fulfilment.type ?? "Missing"}</dd>
        </div>
        <div>
          <dt>Address</dt>
          <dd>{session.fulfilment.address_text ?? "None"}</dd>
        </div>
        <div>
          <dt>Pickup Time</dt>
          <dd>{session.fulfilment.pickup_time ?? "None"}</dd>
        </div>
        <div>
          <dt>Payment</dt>
          <dd>{session.payment_method ?? "Missing"}</dd>
        </div>
      </dl>

      <h3>Cart</h3>
      {session.cart.length === 0 ? (
        <p>No items yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>Item</th>
              <th>Qty</th>
              <th>Size</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {session.cart.map((item) => (
              <tr key={item.line_id}>
                <td>
                  {item.display_name}
                  {item.extra_toppings.length ? <small>Extra: {item.extra_toppings.join(", ")}</small> : null}
                  {item.removed_ingredients.length ? <small>Removed: {item.removed_ingredients.join(", ")}</small> : null}
                </td>
                <td>{item.quantity}</td>
                <td>{item.size ?? "-"}</td>
                <td>{item.line_total_huf.toLocaleString("hu-HU")} Ft</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <div className="total-row">
        <span>Total</span>
        <strong>{session.total_huf.toLocaleString("hu-HU")} Ft</strong>
      </div>

      <div>
        <h3>Missing Fields</h3>
        {session.missing_fields.length ? (
          <ul className="chips">
            {session.missing_fields.map((field) => (
              <li key={field}>{field}</li>
            ))}
          </ul>
        ) : (
          <p>None</p>
        )}
      </div>

      <button type="button" onClick={onConfirm} disabled={!canConfirm || loading}>
        Confirm Order
      </button>
    </section>
  );
}
