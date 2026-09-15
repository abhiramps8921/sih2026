import { Link, useSearchParams } from 'react-router-dom';

const types = ['family', 'group', 'solo'];
export function selectedTravelType(params) {
  return types.includes(params.get('travel_type')) ? params.get('travel_type') : null;
}

export default function TravelType() {
  const [params, setParams] = useSearchParams();
  const selected = selectedTravelType(params);
  return (
    <section className="travel-type" aria-label="Travel type">
      <div className="interest-row">
        {types.map((type) => (
          <button
            key={type}
            type="button"
            className={`interest ${selected === type ? 'selected' : ''}`}
            aria-pressed={selected === type}
            onClick={() => {
              const next = new URLSearchParams(params);
              next.set('travel_type', type);
              setParams(next);
            }}
          >
            {type[0].toUpperCase() + type.slice(1)}
          </button>
        ))}
      </div>
      {selected === 'group' && (
        <div className="tag-options">
          <Link className="button dark" to="/community?action=create&travel_type=group">
            Create group
          </Link>
          <Link className="button" to="/community?action=join&travel_type=group">
            Join group
          </Link>
        </div>
      )}
      {selected === 'family' && (
        <p className="field-hint">
          Family is saved as your preference. Child suitability has not been verified for this
          catalog.
        </p>
      )}
    </section>
  );
}
