import { useEffect, useRef, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { api, send } from './api';
import { useApp } from './context';
import { ErrorNotice, PageHeading } from './components';

const dimensions = [
  [
    'safety',
    'Safety',
    '1: Felt unsafe, with poor access to help. 5: Felt comfortable, with good access and surroundings.',
  ],
  [
    'legitimacy',
    'Legitimacy',
    '1: Misleading listings or hidden charges. 5: Honest information and transparent pricing.',
  ],
  ['hygiene', 'Hygiene', '1: Poor cleanliness and maintenance. 5: Clean and well maintained.'],
];
const empty = {
  safety: null,
  legitimacy: null,
  hygiene: null,
  tip: '',
  tip_category: 'general',
  visit_date: '',
};

export default function Rate() {
  const { places } = useApp();
  const [params, setParams] = useSearchParams();
  const [query, setQuery] = useState('');
  const selected = params.get('place') || '';
  const place = places.find((p) => p.id === selected);
  const matches = places.filter((p) =>
    `${p.name} ${p.area_name} ${p.category}`.toLowerCase().includes(query.toLowerCase()),
  );
  return (
    <main id="main" className="main-shell rate-page">
      <PageHeading
        eyebrow="FROM YOUR OWN EXPERIENCE"
        title="Add a rating or local tip"
        subtitle="Help the next traveler with a little of what you learned."
      />
      <section className="rate-card">
        <h2>Choose a location</h2>
        <label htmlFor="place-search">Search by name, area, or category</label>
        <input
          id="place-search"
          type="search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Try Fort Kochi…"
        />
        <label htmlFor="rate-place">Catalog location (required)</label>
        <select
          id="rate-place"
          value={selected}
          onChange={(e) => setParams(e.target.value ? { place: e.target.value } : {})}
        >
          <option value="">Choose a place</option>
          {place && !matches.includes(place) && (
            <option value={place.id}>
              {place.name} · {place.area_name} · {place.category}
            </option>
          )}
          {matches.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name} · {p.area_name} · {p.category}
            </option>
          ))}
        </select>
        {matches.length === 0 && <p role="status">No matching places. Try another search.</p>}
        {selected && !place && (
          <ErrorNotice error="That location is not in the catalog. Choose a place above." />
        )}
      </section>
      {place && <ContributionForm key={place.id} place={place} />}
    </main>
  );
}

function ContributionForm({ place }) {
  const { refreshCommunity, showSLH } = useApp();
  const [values, setValues] = useState(empty);
  const [rating, setRating] = useState(true);
  const [tip, setTip] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [existing, setExisting] = useState(null);
  const [visited, setVisited] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const inFlight = useRef(false);
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  const path = `/places/${encodeURIComponent(place.id)}/contribution`;
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api(path)
      .then((data) => {
        if (!active) return;
        setVisited(data.self_reported_visit);
        setExisting(data.contribution);
        if (data.contribution) {
          setValues(data.contribution);
          setRating(data.contribution.safety !== null);
          setTip(Boolean(data.contribution.tip));
        }
        setLoading(false);
      })
      .catch((e) => {
        if (active) setError(e.message);
      });
    return () => {
      active = false;
    };
  }, [path, retry]);
  function update(key, value) {
    setValues((previous) => ({ ...previous, [key]: value }));
  }
  async function mutate(remove = false) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const result = await send(
        path,
        remove ? 'DELETE' : 'PUT',
        remove
          ? undefined
          : {
              safety: rating ? values.safety : null,
              legitimacy: rating ? values.legitimacy : null,
              hygiene: rating ? values.hygiene : null,
              tip: tip ? values.tip : '',
              tip_category: tip ? values.tip_category : null,
              visit_date: values.visit_date,
              personal_experience: confirmed,
            },
      );
      setExisting(remove ? null : result);
      setConfirmed(false);
      if (remove) {
        setValues(empty);
        setRating(true);
        setTip(false);
      }
      setMessage(
        remove
          ? 'Your contribution was deleted.'
          : 'Your contribution is saved. Each account has one vote per place.',
      );
      try {
        await refreshCommunity();
      } catch {
        setError(
          'Your change was saved, but scores could not refresh. Reload the page to see current scores.',
        );
      }
    } catch (e) {
      setError(e.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  if (loading)
    return (
      <section className="rate-card" aria-live="polite">
        {error ? (
          <>
            <ErrorNotice error={error} />
            <button className="button dark" onClick={() => setRetry(retry + 1)}>
              Retry loading your contribution
            </button>
          </>
        ) : (
          <p>Loading your contribution…</p>
        )}
      </section>
    );
  return (
    <form
      className="rate-card"
      onSubmit={(e) => {
        e.preventDefault();
        mutate();
      }}
    >
      <h2>
        {existing ? 'Edit your contribution' : 'Your experience'} · {place.name}
      </h2>
      <p className="notice">
        {visited
          ? 'Roam has a self-reported completed visit for this place.'
          : 'Roam has no self-reported completed visit for this place.'}{' '}
        This is not a verified visit.
      </p>
      {existing && existing.tip_status !== 'published' && (
        <p className="notice">
          Your tip is {existing.tip_status} pending review and is not public. Editing it does not
          clear reports. Rating moderation is separate.
        </p>
      )}
      <fieldset disabled={busy}>
        <legend>What would you like to share?</legend>
        <label className="rate-check">
          <input type="checkbox" checked={rating} onChange={(e) => setRating(e.target.checked)} />{' '}
          SLH rating
        </label>
        <label className="rate-check">
          <input type="checkbox" checked={tip} onChange={(e) => setTip(e.target.checked)} /> Local
          tip
        </label>
        {rating &&
          dimensions.map(([key, name, guidance]) => (
            <fieldset className="rating-control" key={key} aria-describedby={`${key}-help`}>
              <legend>{name} (required)</legend>
              <p id={`${key}-help`}>{guidance}</p>
              <div className="rating-options">
                {[1, 2, 3, 4, 5].map((value) => (
                  <label key={value}>
                    <input
                      type="radio"
                      name={key}
                      value={value}
                      checked={values[key] === value}
                      onChange={() => update(key, value)}
                      required
                    />{' '}
                    {value}
                  </label>
                ))}
              </div>
            </fieldset>
          ))}
        {tip && (
          <div className="tip-input">
            <label htmlFor="tip-text">Local tip {rating ? '(optional)' : '(required)'}</label>
            <textarea
              id="tip-text"
              rows="4"
              maxLength={500}
              required={!rating}
              value={values.tip}
              onChange={(e) => update('tip', e.target.value)}
              aria-describedby="tip-help tip-count"
            />
            <small id="tip-count">{values.tip.length} / 500 characters</small>
            <p id="tip-help">
              Share practical advice from your visit. No personal information, advertisements, or
              emergency reports. Use local emergency services for urgent help.
            </p>
            <label htmlFor="tip-category">Category (optional)</label>
            <select
              id="tip-category"
              value={values.tip_category || ''}
              onChange={(e) => update('tip_category', e.target.value || null)}
            >
              <option value="">No category</option>
              {['best time', 'cost', 'accessibility', 'food', 'safety', 'hygiene', 'general'].map(
                (value) => (
                  <option key={value}>{value}</option>
                ),
              )}
            </select>
          </div>
        )}
        <label htmlFor="visit-date">When did you last visit? (required)</label>
        <input
          id="visit-date"
          type="date"
          required
          max={today}
          value={values.visit_date}
          onChange={(e) => update('visit_date', e.target.value)}
        />
        <label className="rate-check">
          <input
            type="checkbox"
            required
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
          />{' '}
          This reflects my personal experience. I understand SLH is community guidance, not a safety
          guarantee.
        </label>
        {!rating && !tip && <p>Select an SLH rating, a local tip, or both.</p>}
        <button className="button dark" type="submit" disabled={!rating && !tip}>
          {busy ? 'Saving…' : existing ? 'Save changes' : 'Submit contribution'}
        </button>
      </fieldset>
      <ErrorNotice error={error} />
      <p role="status">{message}</p>
      <div className="rate-footer">
        <button type="button" className="text-button" onClick={() => showSLH(place)}>
          View current SLH and tips
        </button>
        {existing && (
          <button
            className="text-button"
            type="button"
            disabled={busy}
            onClick={() => mutate(true)}
          >
            Delete my contribution
          </button>
        )}
        <Link to="/slh">How SLH works</Link>
      </div>
    </form>
  );
}
