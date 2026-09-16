import { useState, useEffect } from 'react';
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom';
import {
  ArrowLeft,
  ArrowRight,
  ArrowUpRight,
  Bookmark,
  CalendarDays,
  Check,
  CheckCircle2,
  Clock,
  Footprints,
  Leaf,
  LoaderCircle,
  MapPin,
  Plus,
  Sparkles,
  Wallet,
  ShieldCheck,
  RefreshCw,
  Trash2,
} from 'lucide-react';
import { useApp } from './context';
import { api, send } from './api';
import { templates, money, interests } from './data';
import { PageHeading, ErrorNotice, SLHPill } from './components';
import TripMap from './TripMap';
import TravelType, { selectedTravelType } from './TravelType';

function localDate() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}
const dateLabel = (value) =>
  new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(
    new Date(`${value}T12:00:00`),
  );
const stopChoiceByPace = { relaxed: '3', balanced: 'custom', packed: '5' };

export function Planner() {
  const [params] = useSearchParams();
  const template = templates.find((t) => t.id === params.get('template'));
  const requestedPace = params.get('pace');
  const { refresh, regions } = useApp();
  const navigate = useNavigate();
  const [tags, setTags] = useState(
    interests.includes(params.get('interest')) && params.get('interest') !== 'All experiences'
      ? [params.get('interest')]
      : template?.tags.filter((t) => t !== 'Hidden gems') || ['Culture', 'Food'],
  );
  const [stopChoice, setStopChoice] = useState(stopChoiceByPace[requestedPace] || '5');
  const [customStops, setCustomStops] = useState('4');
  const [includeVisited, setIncludeVisited] = useState(true);
  const [areas, setAreas] = useState(() =>
    regions.filter((region) => region.name === params.get('area')).map((region) => region.id),
  );
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  async function generate(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const form = new FormData(e.currentTarget);
    try {
      const trip = await send('/trips', 'POST', {
        days: Number(form.get('days')),
        budget: Number(form.get('budget')),
        start_date: form.get('date'),
        travel_type: selectedTravelType(params),
        interests: tags,
        custom_request: form.get('custom_request'),
        areas,
        stops_per_day: Number(stopChoice === 'custom' ? customStops : stopChoice),
        min_slh: Number(form.get('slh')),
        template_id: template?.id || null,
        title: form.get('title'),
        include_visited: includeVisited,
      });
      await refresh();
      navigate(`/trips/${trip.id}`);
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="main-shell">
      <Link className="back-link" to="/">
        <ArrowLeft size={16} />
        Back to exploring
      </Link>
      <PageHeading
        eyebrow="MAKE ROOM FOR A GOOD STORY"
        title="A little more you"
        subtitle="Tell us what you love. We’ll connect the dots."
      />
      <div className="planner-layout">
        <form className="form-panel" onSubmit={generate}>
          <div className="panel-title">
            <span className="step-badge">01</span>
            <h2>The essentials</h2>
          </div>
          <div className="fixed-destination">
            <MapPin />
            <div>
              <strong>Kochi, Kerala</strong>
              <p>Our first city. A thousand little discoveries.</p>
            </div>
            <span className="tag">Pilot city</span>
          </div>
          <fieldset className="tag-fieldset">
            <legend>Which parts of Kochi?</legend>
            <p className="field-hint">Leave all unselected for a citywide plan.</p>
            <div className="tag-options">
              {regions.map((region) => (
                <button
                  key={region.id}
                  type="button"
                  aria-pressed={areas.includes(region.id)}
                  className={`interest ${areas.includes(region.id) ? 'selected' : ''}`}
                  onClick={() =>
                    setAreas((previous) =>
                      previous.includes(region.id)
                        ? previous.filter((id) => id !== region.id)
                        : [...previous, region.id],
                    )
                  }
                  title={region.character}
                >
                  {areas.includes(region.id) && <Check size={15} />} {region.name}
                </button>
              ))}
            </div>
          </fieldset>
          <TravelType />
          <label className="field">
            Give your trip a name
            <input
              name="title"
              maxLength="100"
              defaultValue={template?.title || 'My Kochi escape'}
              placeholder="A weekend to remember…"
              autoComplete="off"
              required
            />
          </label>
          <div className="form-grid">
            <label className="field">
              Starting date
              <input
                name="date"
                type="date"
                defaultValue={localDate()}
                min={localDate()}
                required
              />
            </label>
            <label className="field">
              How many days?
              <select name="days" defaultValue={template?.days || 2}>
                {[1, 2, 3].map((d) => (
                  <option value={d} key={d}>
                    {d} {d === 1 ? 'day' : 'days'}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <label className="field">
            Daily budget per person
            <div className="money-input">
              <span>₹</span>
              <input
                name="budget"
                type="number"
                inputMode="numeric"
                min="500"
                max="20000"
                step="50"
                defaultValue="1500"
                required
              />
            </div>
            <small>Includes food, visits & local travel. Excludes accommodation.</small>
          </label>
          <div className="panel-title spaced">
            <span className="step-badge">02</span>
            <h2>Your kind of day</h2>
          </div>
          <fieldset className="tag-fieldset">
            <legend>What draws you in?</legend>
            <div className="tag-options">
              {['Food', 'Culture', 'Nature', 'Art', 'Hidden gems', 'Shopping'].map((t) => (
                <button
                  key={t}
                  type="button"
                  aria-pressed={tags.includes(t)}
                  className={`interest ${tags.includes(t) ? 'selected' : ''}`}
                  onClick={() =>
                    setTags((prev) =>
                      prev.includes(t) ? prev.filter((x) => x !== t) : [...prev, t],
                    )
                  }
                >
                  {tags.includes(t) && <Check size={15} />} {t}
                </button>
              ))}
            </div>
          </fieldset>
          <fieldset className="tag-fieldset">
            <legend>How many stops in a day?</legend>
            <p className="field-hint">
              Your target per day. Visits, travel, opening hours and 20-minute breaks must fit
              between 09:00 and 22:00.
            </p>
            <div className="pace-grid">
              {[
                ['3', '3 stops', 'A slower day', Leaf],
                ['5', '5 stops', 'See a little more', Sparkles],
                ['custom', 'Custom', 'Up to 20 stops', Plus],
              ].map(([value, title, sub, Icon]) => (
                <label
                  key={value}
                  className={`pace-choice ${stopChoice === value ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="stop-choice"
                    value={value}
                    checked={stopChoice === value}
                    onChange={() => setStopChoice(value)}
                  />
                  <Icon size={20} />
                  <strong>{title}</strong>
                  <small>{sub}</small>
                  {value === 'custom' && stopChoice === 'custom' && (
                    <input
                      className="custom-stop-input"
                      type="number"
                      inputMode="numeric"
                      min="1"
                      max="20"
                      step="1"
                      value={customStops}
                      onChange={(event) => setCustomStops(event.target.value)}
                      aria-label="Custom stops per day"
                      required
                    />
                  )}
                </label>
              ))}
            </div>
            <p className="field-hint stop-count-hint">
              Opening hours, travel time, and budget may reduce the final number of stops.
            </p>
          </fieldset>
          <fieldset className="tag-fieldset">
            <legend>Places you’ve already visited</legend>
            <div className="pace-grid visited-choice-grid">
              {[
                [true, 'Include them', 'Mix favourites with new discoveries'],
                [false, 'New places only', 'Leave previously completed places out'],
              ].map(([value, title, sub]) => (
                <label
                  key={String(value)}
                  className={`pace-choice ${includeVisited === value ? 'selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="include-visited"
                    checked={includeVisited === value}
                    onChange={() => setIncludeVisited(value)}
                  />
                  <MapPin size={20} />
                  <strong>{title}</strong>
                  <small>{sub}</small>
                </label>
              ))}
            </div>
            <p className="field-hint stop-count-hint">
              A place joins your visited history when you mark that stop complete.
            </p>
          </fieldset>
          <label className="field">
            Minimum SLH score
            <select name="slh" defaultValue="0">
              <option value="0">All places — show the full picture</option>
              <option value="80">80+ — higher sample ratings</option>
              <option value="90">90+ — highest sample ratings</option>
            </select>
            <small>SLH ratings are illustrative demo data, not guarantees.</small>
          </label>
          <label className="field">
            Describe the kind of trip you want (optional)
            <textarea
              name="custom_request"
              maxLength={2000}
              rows={3}
              placeholder="A relaxed trip with local food and somewhere nice for sunset..."
            />
            <small>When AI is available, your preferences help shape the itinerary.</small>
          </label>
          <ErrorNotice error={error} />
          <button className="button dark full" disabled={busy}>
            {busy ? <LoaderCircle className="spin" size={18} /> : <Sparkles size={18} />}{' '}
            {busy ? 'Putting your trip together…' : 'Build & save my itinerary'}
            <ArrowRight size={18} />
          </button>
        </form>
        <aside className="planner-aside">
          <img
            className="planner-image"
            src="/images/kochi.jpg"
            alt="Evening light behind Kochi fishing nets"
            width="650"
            height="500"
          />
          <div className="planner-aside-copy">
            <span className="eyebrow">LESS PLANNING. MORE BEING THERE.</span>
            <h2>
              The best trips leave
              <br />
              room for a little wonder.
            </h2>
            <ul className="benefit-list">
              <li>
                <MapPin size={18} />
                <span>Nearby stops, thoughtfully ordered</span>
              </li>
              <li>
                <Clock size={18} />
                <span>Time for food, travel & slowing down</span>
              </li>
              <li>
                <ShieldCheck size={18} />
                <span>SLH details for every place</span>
              </li>
              <li>
                <Wallet size={18} />
                <span>Clear estimates for your budget</span>
              </li>
            </ul>
            <p className="notice">
              This pilot uses a rule-based planner and sample venue information. Walking and local
              transit times are estimates; check opening hours locally.
            </p>
          </div>
        </aside>
      </div>
    </main>
  );
}

export function Itinerary() {
  const { id } = useParams();
  const { places, me, toggleSave, showSLH } = useApp();
  const [params, setParams] = useSearchParams();
  const template = templates.find((t) => t.id === id);
  if (!template)
    return (
      <main id="main" className="main-shell">
        <div className="empty-state">
          <h1>Trip not found.</h1>
          <Link to="/">Back to Explore</Link>
        </div>
      </main>
    );
  const day = Math.min(template.days, Math.max(1, Math.floor(Number(params.get('day')) || 1)));
  const split = Math.ceil(template.stops.length / template.days);
  const selected = template.stops
    .slice((day - 1) * split, day * split)
    .map((id) => places.find((p) => p.id === id))
    .filter(Boolean);
  const stops = selected.map((place, i) => ({ place, id: place.id, start: `${9 + i * 2}:00` }));
  return (
    <main className="main-shell" id="main">
      <Link className="back-link" to="/">
        <ArrowLeft size={16} />
        The local edit
      </Link>
      <div className="detail-hero">
        <img src={template.image} alt={template.imageAlt} width="1200" height="650" />
        <div className="detail-shade" />
        <div className="detail-title">
          <span className="glass-label">{template.category.toUpperCase()} · KOCHI</span>
          <h1>{template.title}</h1>
          <p>{template.subtitle}</p>
          <div className="detail-creator">
            <span className="avatar" style={{ background: template.color }}>
              {template.initials}
            </span>
            By {template.creator} · Sample contributor
          </div>
        </div>
        <button className="button white detail-save" onClick={() => toggleSave(id)}>
          <Bookmark size={17} fill={me.saved.includes(id) ? 'currentColor' : 'none'} />
          {me.saved.includes(id) ? 'Saved' : 'Save trip'}
        </button>
      </div>
      <div className="detail-facts">
        <span>
          <CalendarDays size={18} />
          {template.days} {template.days === 1 ? 'day' : 'days'}
        </span>
        <span>
          <MapPin size={18} />
          {template.stops.length} stops
        </span>
        <span>
          <Wallet size={18} />
          From {money(template.cost)} / person
        </span>
        <Link
          className="button dark"
          to={`/plan?${new URLSearchParams({ ...Object.fromEntries(params), template: id })}`}
        >
          Plan a trip
          <ArrowRight size={17} />
        </Link>
      </div>
      <div className="trip-detail-grid">
        <section>
          <div className="section-heading">
            <h2>A good day, one stop at a time.</h2>
          </div>
          <div className="day-tabs" aria-label="Itinerary day">
            {Array.from({ length: template.days }, (_, i) => (
              <button
                key={i}
                aria-pressed={day === i + 1}
                className={day === i + 1 ? 'active' : ''}
                onClick={() => {
                  const next = new URLSearchParams(params);
                  next.set('day', i + 1);
                  setParams(next);
                }}
              >
                Day {i + 1}
              </button>
            ))}
          </div>
          <p className="small-copy">
            Suggested order. Personalize this trip for a timed, budget-aware schedule.
          </p>
          <div className="timeline">
            {stops.map((s, i) => (
              <article className="stop-card" key={s.id}>
                <span className="stop-number">{i + 1}</span>
                <div className="stop-body">
                  <div className="stop-heading">
                    <span className="tag">{s.place.category}</span>
                    <SLHPill slh={s.place.slh} onClick={() => showSLH(s.place)} />
                  </div>
                  <h3>{s.place.name}</h3>
                  <p>{s.place.tip}</p>
                  <div className="stop-facts">
                    <span>
                      <Clock size={14} />
                      {s.place.duration} min
                    </span>
                    <span>{s.place.cost ? money(s.place.cost) : 'Free entry estimate'}</span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
        <aside className="map-aside">
          <TripMap stops={stops} />
          <div className="notice">
            <strong>A starting point, not a rigid checklist.</strong>
            <br />
            Personalize this collection to get travel estimates, time slots and a plan saved just
            for you.
          </div>
        </aside>
      </div>
    </main>
  );
}

export function MyTrips() {
  const { me } = useApp();
  const [params, setParams] = useSearchParams();
  const saved = params.get('tab') === 'saved';
  return (
    <main className="main-shell" id="main">
      <PageHeading
        eyebrow="LITTLE PLANS. BIG MEMORIES."
        title="Your next chapters"
        subtitle="Pick up where you left off, or start a new story."
        action={
          <Link className="button dark" to="/plan">
            <Plus size={17} />
            Plan a trip
          </Link>
        }
      />
      <div className="day-tabs">
        <button
          className={!saved ? 'active' : ''}
          aria-pressed={!saved}
          onClick={() => setParams({})}
        >
          My itineraries <span>{me.trips.length}</span>
        </button>
        <button
          className={saved ? 'active' : ''}
          aria-pressed={saved}
          onClick={() => setParams({ tab: 'saved' })}
        >
          Saved collection <span>{me.saved.length}</span>
        </button>
      </div>
      <div className="saved-grid">
        {saved
          ? templates
              .filter((t) => me.saved.includes(t.id))
              .map((t) => (
                <Link key={t.id} className="saved-trip" to={`/itinerary/${t.id}`}>
                  <img src={t.image} alt="" width="600" height="350" />
                  <div>
                    <span className="eyebrow">{t.category}</span>
                    <h2>{t.title}</h2>
                    <p>
                      {t.days} days · From {money(t.cost)}
                    </p>
                    <span className="text-button">
                      View itinerary
                      <ArrowUpRight size={17} />
                    </span>
                  </div>
                </Link>
              ))
          : me.trips.map((t) => {
              const stops = t.days.flatMap((d) => d.stops);
              const completed = stops.filter((s) => s.completed).length;
              return (
                <Link key={t.id} className="saved-trip" to={`/trips/${t.id}`}>
                  <img src="/images/kochi.jpg" alt="" width="600" height="350" />
                  <div>
                    <span className="eyebrow">
                      {completed === stops.length ? 'A STORY WELL TRAVELLED' : 'KOCHI, KERALA'}
                    </span>
                    <h2>{t.title}</h2>
                    <p>
                      {dateLabel(t.days[0].date)} · {t.days.length} days · {money(t.total_cost)}
                    </p>
                    <progress max={stops.length} value={completed} />
                    <div className="progress-caption">
                      <span>
                        {completed} of {stops.length} stops complete
                      </span>
                      <ArrowUpRight size={18} />
                    </div>
                  </div>
                </Link>
              );
            })}
      </div>
      {(saved ? me.saved.length === 0 : me.trips.length === 0) && (
        <div className="empty-state">
          <MapPin size={32} />
          <h2>{saved ? 'Keep a little inspiration.' : 'Your story is still unwritten.'}</h2>
          <p>
            {saved
              ? 'Save an itinerary from Explore to find it here.'
              : 'Build your first itinerary and make it a trip to remember.'}
          </p>
          <Link className="button dark" to={saved ? '/' : '/plan'}>
            {saved ? 'Explore trips' : 'Plan a trip'}
            <ArrowRight size={17} />
          </Link>
        </div>
      )}
    </main>
  );
}

export function ActiveTrip() {
  const { id } = useParams();
  const { refresh, showSLH, notify } = useApp();
  const [trip, setTrip] = useState(null);
  const [focusRequest, setFocusRequest] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    let live = true;
    api(`/trips/${id}`)
      .then((t) => {
        if (live) setTrip(t);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [id]);
  async function toggle(stop) {
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      setTrip(await send(`/trips/${id}/stops/${stop.id}`, 'PUT', { completed: !stop.completed }));
      await refresh();
      notify(
        stop.completed ? 'Completion undone. Points updated.' : 'One more memory made. +10 points!',
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function editStop(stop, action) {
    if (busy) return;
    if (
      !window.confirm(
        action === 'replace'
          ? 'Replace this stop and rebuild the schedule? Other stops may move to keep the trip feasible.'
          : 'Remove this stop and update this day’s timing and cost?',
      )
    )
      return;
    setBusy(true);
    setError('');
    try {
      setTrip(await send(`/trips/${id}`, 'PATCH', { stop_id: stop.id, action }));
      await refresh();
      notify(
        action === 'replace'
          ? 'Stop replaced. Your schedule and map are updated.'
          : 'Stop removed. Timing and costs updated.',
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  if (!trip)
    return (
      <main id="main" className="main-shell">
        <ErrorNotice error={error} />
        {!error && <p>Opening your itinerary…</p>}
        <Link className="back-link" to="/trips">
          Back to My trips
        </Link>
      </main>
    );
  const dayIndex = Math.min(
    trip.days.length - 1,
    Math.max(0, Math.floor(Number(params.get('day')) || 1) - 1),
  );
  const day = trip.days[dayIndex];
  const allStops = trip.days.flatMap((d) => d.stops);
  const done = allStops.filter((s) => s.completed).length;
  function viewRoute(stop) {
    setFocusRequest({ stopId: stop.id });
    const map = document.getElementById('itinerary-map');
    map?.focus({ preventScroll: true });
    map?.scrollIntoView({
      behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches
        ? 'instant'
        : 'smooth',
      block: 'center',
    });
  }
  return (
    <main id="main" className="main-shell">
      <Link className="back-link" to="/trips">
        <ArrowLeft size={16} />
        My trips
      </Link>
      <PageHeading
        eyebrow="YOUR PLAN. YOUR PACE."
        title={trip.title}
        subtitle={`${dateLabel(trip.days[0].date)} · ${trip.days.length} ${trip.days.length === 1 ? 'day' : 'days'} in Kochi`}
        action={
          <span className="plan-saved">
            <CheckCircle2 size={18} />
            Saved to your trips
          </span>
        }
      />
      <div className="trip-summary">
        <div>
          <Wallet size={22} />
          <span>
            <small>ESTIMATED TOTAL</small>
            <strong>
              {money(trip.total_cost)} <small>/ person</small>
            </strong>
            {Number.isFinite(trip.budget_utilization) && (
              <small>{trip.budget_utilization}% of the planned budget</small>
            )}
          </span>
        </div>
        <div>
          <Footprints size={22} />
          <span>
            <small>YOUR PROGRESS</small>
            <strong>
              {done} of {allStops.length} stops
            </strong>
          </span>
        </div>
        <div className="summary-progress">
          <progress value={done} max={allStops.length} />
          <small>
            {done === allStops.length
              ? 'A story well travelled. Your badge is waiting.'
              : 'Little steps make the best stories.'}
          </small>
        </div>
      </div>
      <ErrorNotice error={error} />
      {trip.warnings.map((w) => (
        <p className="notice" key={w}>
          {w}
        </p>
      ))}
      <div className="trip-detail-grid">
        <section>
          <div className="day-tabs">
            {trip.days.map((d, i) => (
              <button
                key={d.day}
                className={i === dayIndex ? 'active' : ''}
                aria-pressed={i === dayIndex}
                onClick={() => setParams({ day: d.day })}
              >
                Day {d.day}
                <small>{dateLabel(d.date)}</small>
              </button>
            ))}
          </div>
          <div className="day-intro">
            <h2>
              {dayIndex === 0 ? 'Let the wandering begin.' : 'Another day, another discovery.'}
            </h2>
            <p>
              {day.stops.length} stops scheduled
              {trip.preferences?.stops_per_day &&
                ` · ${trip.preferences.stops_per_day} requested per day`}
            </p>
            <p>
              {money(day.cost)} estimated
              {Number.isFinite(day.budget_utilization) &&
                ` · ${day.budget_utilization}% of daily budget`}{' '}
              {day.area_clustered && '· Area-clustered route '}· 20-minute breaks
            </p>
          </div>
          <div className="timeline">
            {day.stops.map((stop, i) => (
              <article className={`stop-card ${stop.completed ? 'is-complete' : ''}`} key={stop.id}>
                <span className="stop-number">
                  {stop.completed ? <Check size={16} /> : (stop.number ?? i + 1)}
                </span>
                <div className="stop-body">
                  <div className="stop-heading">
                    <span className="stop-time">
                      {stop.start} — {stop.end}
                    </span>
                    <SLHPill slh={stop.place.slh} onClick={() => showSLH(stop.place)} />
                  </div>
                  <h3>{stop.place.name}</h3>
                  <p>{stop.place.tip}</p>
                  <div className="stop-facts">
                    <span>
                      <Clock size={14} />
                      {stop.place.duration} min
                    </span>
                    <span>{money(stop.place.cost)}</span>
                    {stop.place.price_tier === 'premium' && <span>Premium experience</span>}
                    <span>
                      <Footprints size={14} />
                      {stop.travel_mode === 'start'
                        ? `Start in ${stop.place.area_name}`
                        : `~${stop.travel_minutes} min by ${stop.travel_mode}`}
                    </span>
                  </div>
                  {done === 0 && (
                    <div className="edit-stop-actions">
                      <button disabled={busy} onClick={() => editStop(stop, 'replace')}>
                        <RefreshCw size={14} />
                        Replace stop
                      </button>
                      <button disabled={busy} onClick={() => editStop(stop, 'remove')}>
                        <Trash2 size={14} />
                        Remove
                      </button>
                    </div>
                  )}
                  <div className="stop-actions">
                    <button
                      disabled={busy}
                      className={`complete-button ${stop.completed ? 'complete' : ''}`}
                      onClick={() => toggle(stop)}
                    >
                      <CheckCircle2 size={16} />
                      {stop.completed ? 'Completed · Undo' : 'Mark as complete'}
                    </button>
                    <div className="route-actions">
                      <button
                        type="button"
                        className="navigation-link"
                        onClick={() => viewRoute(stop)}
                        aria-label={`Show ${stop.place.name} on the itinerary map`}
                        aria-controls="itinerary-map"
                      >
                        <MapPin size={15} />
                        Show on map
                      </button>
                      <a
                        className="navigation-link external-navigation-link"
                        href={`https://www.google.com/maps/dir/?api=1&destination=${encodeURIComponent([stop.place.name, stop.place.area_name, 'Kochi', 'Kerala'].filter(Boolean).join(', '))}`}
                        target="_blank"
                        rel="noopener noreferrer"
                        aria-label={`Get directions from your location to ${stop.place.name} in Google Maps (opens in a new tab)`}
                      >
                        View in Google Maps
                        <ArrowUpRight size={15} />
                      </a>
                    </div>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
        <aside className="map-aside">
          <TripMap stops={day.stops} focusRequest={focusRequest} />
          <div className="local-tip">
            <Leaf size={22} />
            <h3>A little local wisdom</h3>
            <p>Carry water, give yourself time, and ask before taking someone’s photograph.</p>
          </div>
          <p className="notice">{trip.cost_note}</p>
          <p className="small-copy">
            {trip.method}. Self-reported completion earns points; it does not verify a visit. SLH
            scores are sample data.
          </p>
        </aside>
      </div>
    </main>
  );
}
