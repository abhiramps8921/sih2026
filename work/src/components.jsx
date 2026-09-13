import { useEffect, useRef } from 'react';
import { ShieldCheck, X, CheckCircle2, BadgeCheck, Droplets } from 'lucide-react';
import { slhScore } from './data';
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
      <small>DEMO</small>
    </button>
  );
}
export function SLHDetails({ place, close }) {
  const ref = useRef(null);
  useEffect(() => {
    const trigger = document.activeElement;
    ref.current.showModal();
    return () => trigger?.focus();
  }, []);
  const slh = place.slh;
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
          <p>Illustrative community rating</p>
        </div>
        <ShieldCheck size={42} />
      </div>
      <div className="rating-list">
        {[
          ['Safety', 'safety', ShieldCheck, 'Comfort, access & surroundings'],
          ['Legitimacy', 'legitimacy', BadgeCheck, 'Accurate listings & transparent pricing'],
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
        <strong>Sample data, not a safety guarantee.</strong> {slh?.reviews || 0} illustrative
        reviews · Sample date {slh?.reviewed_at}. No live reviews have been collected.
      </p>
      <p className="small-copy">
        Equal-weight average of the three dimensions, converted to 100. Check recent local
        information before visiting.
      </p>
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
