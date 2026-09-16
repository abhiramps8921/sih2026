import { useEffect, useRef } from 'react';
import { ShieldCheck, X, CheckCircle2, BadgeCheck, Droplets } from 'lucide-react';
import { slhScore } from './data';
import { Link } from 'react-router-dom';
import { useApp } from './context';
import CommunityTips from './CommunityTips';
export function SLHPill({ slh, onClick }) {
  const score = slhScore(slh);
  return (
    <button
      className="slh-pill slh-button"
      onClick={onClick}
      aria-label={`SLH ${score ?? 'unrated'}: view Safety, Legitimacy and Hygiene details`}
    >
      <ShieldCheck size={14} />
      <span>SLH {score ?? '—'}</span>
      <small>
        {score === null
          ? 'UNRATED'
          : slh?.source === 'community'
            ? 'COMMUNITY'
            : slh?.source === 'mixed'
              ? 'MIXED'
              : 'DEMO'}
      </small>
    </button>
  );
}
export function SLHDetails({ place: initialPlace, close }) {
  const { places } = useApp();
  const place = places.find((p) => p.id === initialPlace.id) || initialPlace;
  const ref = useRef(null);
  useEffect(() => {
    const trigger = document.activeElement;
    ref.current.showModal();
    return () => trigger?.focus();
  }, []);
  const slh = place.community_slh || place.slh;
  return (
    <dialog
      ref={ref}
      className="slh-dialog"
      onCancel={close}
      aria-labelledby="slh-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) close();
      }}
    >
      <div className="dialog-heading">
        <span className="eyebrow">KNOW YOUR NEXT STOP</span>
        <button className="icon-button" onClick={close} aria-label="Close SLH details">
          <X size={20} />
        </button>
      </div>
      <h2 id="slh-title">{place.name}</h2>
      <div className="score-hero">
        <span>{slhScore(slh) ?? '—'}</span>
        <div>
          <strong>SLH score / 100</strong>
          <p>
            {place.community_slh
              ? 'Unverified community rating'
              : slhScore(slh) === null
                ? 'Unrated · No eligible SLH data'
                : slh?.source === 'mixed'
                  ? 'Mixed demo and community stop scores'
                  : slh?.source === 'community'
                    ? 'Community stop scores'
                    : 'DEMO · Illustrative seed data'}
          </p>
        </div>
        <ShieldCheck size={42} />
      </div>
      <div className="rating-list">
        {[
          ['Safety', 'safety', ShieldCheck, 'Comfort, access & surroundings'],
          [
            'Legitimacy',
            'legitimacy',
            BadgeCheck,
            'Scam resistance, honest listings & transparent pricing',
          ],
          ['Hygiene', 'hygiene', Droplets, 'Cleanliness & maintenance'],
        ].map(([name, key, Icon, description]) => (
          <div className="rating-item" key={key}>
            <Icon size={21} />
            <div>
              <strong>{name}</strong>
              <small>{description}</small>
              <progress max="5" value={slh?.[key] || 0} />
            </div>
            <b>
              {slh?.[key]?.toFixed(1) ?? '—'}
              <small> / 5</small>
            </b>
          </div>
        ))}
      </div>
      <p className="notice">
        <strong>Community guidance, not a safety guarantee.</strong>{' '}
        {place.community_slh
          ? `${slh.reviews} community rating(s) · Latest ${slh.reviewed_at.slice(0, 10)}.`
          : place.id
            ? 'No community ratings for this place yet.'
            : 'Itinerary score averages the current stop scores; sources may differ by stop.'}
        {place.community_slh &&
          slh.reviews < 3 &&
          ' Early community signal: fewer than three distinct accounts. Planning uses DEMO data where available and otherwise remains unrated.'}
      </p>
      <p className="small-copy">
        Equal-weight average of the three dimensions, converted to 100. Check recent local
        information before visiting.
      </p>
      {place.demo_slh && (
        <section className="demo-score">
          <h3>DEMO · Separate illustrative values</h3>
          <p>
            SLH {slhScore(place.demo_slh) ?? 'unrated'} · Safety {place.demo_slh.safety ?? '—'} ·
            Legitimacy {place.demo_slh.legitimacy ?? '—'} · Hygiene {place.demo_slh.hygiene ?? '—'}
          </p>
          <small>
            {place.demo_slh.reviews || 0} sample reviews ·{' '}
            {place.demo_slh.reviewed_at || 'No sample date'}. These values are never averaged with
            community submissions.
          </small>
        </section>
      )}
      {place.id && (
        <>
          <Link
            className="button dark full"
            to={`/rate?place=${encodeURIComponent(place.id)}`}
            onClick={close}
          >
            Add / edit your rating or tip
          </Link>
          <CommunityTips key={place.id} placeId={place.id} close={close} />
        </>
      )}
      <button className="button dark full" onClick={close}>
        <CheckCircle2 size={17} />
        Got it
      </button>
    </dialog>
  );
}
export function PageHeading({ eyebrow, title, subtitle, action }) {
  return (
    <div className="page-heading">
      <div>
        <div className="eyebrow">
          <span className="tiny-line" />
          {eyebrow}
        </div>
        <h1>
          {title}
          <span>.</span>
        </h1>
        {subtitle && <p>{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}
export function ErrorNotice({ error }) {
  return error ? (
    <p className="error-notice" role="alert">
      {error}
    </p>
  ) : null;
}
