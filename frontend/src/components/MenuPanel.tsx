import { MenuPayload } from "../api";

type Props = {
  menu: MenuPayload | null;
};

export function MenuPanel({ menu }: Props) {
  return (
    <section className="panel menu-panel">
      <div className="panel-header">
        <h2>Menu</h2>
      </div>
      {menu ? (
        <div className="menu-list">
          {menu.items.map((item) => (
            <article key={item.id} className="menu-item">
              <div>
                <strong>{item.name_hu}</strong>
                <span>{item.available ? "Available" : "Unavailable"}</span>
              </div>
              <p>
                {item.sizes.length
                  ? item.sizes.map((size) => `${size.label}: ${size.price_huf.toLocaleString("hu-HU")} Ft`).join(" / ")
                  : `${item.base_price_huf.toLocaleString("hu-HU")} Ft`}
              </p>
              {item.allowed_extra_toppings.length ? <small>Extras: {item.allowed_extra_toppings.join(", ")}</small> : null}
            </article>
          ))}
        </div>
      ) : (
        <p>Loading menu.</p>
      )}
    </section>
  );
}
