import { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { api, send } from './api';
import { ErrorNotice } from './components';

export default function CommunityTips({ placeId, close }) {
  const [tips, setTips] = useState([]);
  const [next, setNext] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [reported, setReported] = useState('');
  const [busy, setBusy] = useState(false);
  const [retry, setRetry] = useState(0);
  const inFlight = useRef(false);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api(`/places/${encodeURIComponent(placeId)}/tips`)
      .then((data) => {
        if (active) {
          setTips(data.tips);
          setNext(data.next_offset);
        }
      })
      .catch((e) => {
        if (active) setError(e.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [placeId, retry]);
  async function act(id) {
    if (inFlight.current) return;
    inFlight.current = true;
    setBusy(true);
    setError('');
    try {
      if (id) {
        await send(`/tips/${encodeURIComponent(id)}/reports`, 'POST', {});
        setReported('Tip reported and removed from public display pending review.');
        setRetry((n) => n + 1);
      } else {
        const data = await api(`/places/${encodeURIComponent(placeId)}/tips?offset=${next}`);
        setTips((old) => [...new Map([...old, ...data.tips].map((t) => [t.id, t])).values()]);
        setNext(data.next_offset);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      inFlight.current = false;
      setBusy(false);
    }
  }
  return (
    <section className="community-tips">
      <h3>Community tips</h3>
      {loading ? (
        <p role="status">Loading tips…</p>
      ) : !tips.length && !error ? (
        <p>No public tips yet. Share what helped on your visit.</p>
      ) : null}
      <ErrorNotice error={error} />
      {error && (
        <button onClick={() => setRetry((n) => n + 1)} disabled={busy}>
          Retry tips
        </button>
      )}
      {tips.map((tip) => (
        <article key={tip.id} className="community-tip">
          <small>
            Unverified community tip · {tip.tip_category || 'general'} · Visited {tip.visit_date}
          </small>
          <p>{tip.tip}</p>
          {tip.is_owner ? (
            <Link to={`/rate?place=${encodeURIComponent(placeId)}`} onClick={close}>
              Edit your contribution
            </Link>
          ) : (
            <button className="text-button" disabled={busy} onClick={() => act(tip.id)}>
              Report inappropriate tip
            </button>
          )}
        </article>
      ))}
      {next !== null && (
        <button className="text-button" disabled={busy} onClick={() => act()}>
          Load more tips
        </button>
      )}
      <p role="status">{reported}</p>
    </section>
  );
}
