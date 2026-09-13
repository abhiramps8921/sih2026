import { useState, useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  ArrowUpRight,
  Award,
  Check,
  CheckCircle2,
  Clock,
  FileText,
  Footprints,
  Leaf,
  LoaderCircle,
  MapPin,
  MessageCircle,
  Plus,
  ShieldCheck,
  Sparkles,
  Users,
  Wallet,
  BadgeCheck,
  Droplets,
} from 'lucide-react';
import { useApp } from './context';
import { api, send } from './api';
import { PageHeading, ErrorNotice, SLHPill } from './components';

export function Community() {
  const [groups, setGroups] = useState([]);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState('');
  const { notify } = useApp();
  useEffect(() => {
    api('/groups')
      .then(setGroups)
      .catch((e) => setError(e.message));
  }, []);
  async function request(group) {
    setBusy(group.id);
    setError('');
    try {
      await send(`/groups/${group.id}`, 'PUT', { saved: !group.status });
      setGroups(await api('/groups'));
      notify(
        group.status
          ? 'Demo request withdrawn.'
          : 'Demo request saved. No real person was contacted.',
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy('');
    }
  }
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="SOME STORIES ARE BETTER SHARED"
        title="Find your kind of people"
        subtitle="Shared interests. A common route. A new conversation."
        action={
          <Link className="button dark" to="/create">
            <Plus size={17} />
            Share your experience
          </Link>
        }
      />
      <div className="community-banner">
        <span className="community-symbol">
          <Users size={35} />
        </span>
        <div>
          <span className="eyebrow">THE COMPANY MAKES THE JOURNEY</span>
          <h2>Solo doesn’t have to mean alone.</h2>
          <p>Explore sample departures and try the request-to-join flow.</p>
        </div>
        <span className="tag">Demo community</span>
      </div>
      <div className="section-heading">
        <div>
          <h2>A few good people, a little adventure.</h2>
          <p>Sample group trips in Kochi · No live matching</p>
        </div>
      </div>
      <ErrorNotice error={error} />
      <div className="community-grid">
        {groups.map((g, i) => (
          <article className="group-card" key={g.id}>
            <img
              src={i ? '/images/heritage.jpg' : '/images/kochi.jpg'}
              alt={i ? 'Mattancherry Palace interior' : 'Kochi waterfront'}
              width="750"
              height="400"
              loading="lazy"
            />
            <div className="group-body">
              <div className="card-meta">
                <span className="tag">Sample departure</span>
                <span>
                  <Users size={14} />
                  {g.members} / {g.capacity} sample spots
                </span>
              </div>
              <h2>{g.title}</h2>
              <div className="group-facts">
                <span>
                  <Clock size={16} />
                  {new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'long' }).format(
                    new Date(g.date + 'T12:00:00'),
                  )}{' '}
                  · {g.time}
                </span>
                <span>
                  <MapPin size={16} />
                  {g.place}
                </span>
              </div>
              <div className="tag-options">
                {g.tags.map((t) => (
                  <span key={t} className="tag">
                    {t}
                  </span>
                ))}
              </div>
              <div className="group-host">
                <span className="avatar">{g.initials}</span>
                <span>
                  Hosted by {g.host}
                  <small>Sample profile</small>
                </span>
                <button
                  className={`button ${g.status ? '' : 'dark'}`}
                  onClick={() => request(g)}
                  disabled={!!busy}
                >
                  {busy === g.id ? (
                    <LoaderCircle className="spin" size={16} />
                  ) : g.status ? (
                    <Check size={16} />
                  ) : (
                    <Plus size={16} />
                  )}{' '}
                  {g.status ? 'Withdraw request' : 'Try join request'}
                </button>
              </div>
              {g.status && (
                <p className="small-copy">
                  Demo request pending. There is no live host approval or chat.
                </p>
              )}
            </div>
          </article>
        ))}
      </div>
      <section className="community-principles">
        <div>
          <ShieldCheck />
          <h3>Your choice, always</h3>
          <p>No public discovery without opting in. Your private itinerary stays yours.</p>
        </div>
        <div>
          <MapPin />
          <h3>Meet in public</h3>
          <p>Public, popular places make better meeting points. Never share your stay address.</p>
        </div>
        <div>
          <MessageCircle />
          <h3>Real connection, thoughtfully</h3>
          <p>
            Verified accounts, reporting, blocking and group chat are planned before public
            matching.
          </p>
        </div>
      </section>
      <p className="notice">
        This is a social feature demonstration. Requests are saved only for your guest session; no
        real travelers are contacted and no meetup is arranged.
      </p>
    </main>
  );
}

export function CreateTrip() {
  const { places, notify, refresh } = useApp();
  const navigate = useNavigate();
  const [drafts, setDrafts] = useState([]);
  const [aiEnabled, setAiEnabled] = useState(false);
  const [editing, setEditing] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [dirty, setDirty] = useState(false);
  useEffect(() => {
    api('/drafts')
      .then(setDrafts)
      .catch((e) => setError(e.message));
    api('/config')
      .then((c) => setAiEnabled(c.ai_enabled))
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    const handler = (e) => {
      if (dirty) {
        e.preventDefault();
        e.returnValue = '';
      }
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [dirty]);
  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError('');
    const f = new FormData(e.currentTarget);
    try {
      const result = editing
        ? await send(`/drafts/${editing.id}`, 'PUT', {
            title: f.get('title'),
            notes: f.get('notes'),
            place_ids: f.getAll('places'),
          })
        : await send('/drafts', 'POST', {
            title: f.get('title'),
            notes: f.get('notes'),
            use_ai: f.get('use_ai') === 'on',
          });
      setEditing(result);
      setDirty(false);
      setDrafts(await api('/drafts'));
      notify(
        editing
          ? 'Your draft changes are saved.'
          : 'Your story is saved. Review the recognized places.',
      );
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  async function schedule() {
    if (dirty) {
      setError('Save your reviewed draft before creating the schedule.');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const trip = await send('/draft-trips', 'POST', {
        draft_id: editing.id,
        days: Math.min(3, Math.max(1, Math.ceil(editing.place_ids.length / 4))),
        budget: 1500,
        interests: [],
        pace: 'balanced',
      });
      await refresh();
      navigate(`/trips/${trip.id}`);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="YOUR EXPERIENCE COULD BE SOMEONE’S FAVOURITE TRIP"
        title="Pass on a good story"
        subtitle="The places you loved. The food you still think about. The tips only you know."
      />
      <div className="planner-layout">
        <form
          key={editing?.id || 'new'}
          className="form-panel"
          onSubmit={submit}
          onChange={() => setDirty(true)}
        >
          <div className="panel-title">
            <FileText size={22} />
            <h2>{editing ? 'Review your trip draft' : 'Tell us about your trip'}</h2>
          </div>
          <label className="field">
            A name for your story
            <input
              name="title"
              minLength="3"
              maxLength="100"
              required
              autoComplete="off"
              defaultValue={editing?.title || ''}
              placeholder="From Thrippunithura to Marine Drive…"
            />
          </label>
          <label className="field">
            Your experience
            <textarea
              name="notes"
              minLength="20"
              maxLength="10000"
              rows="9"
              required
              defaultValue={editing?.notes || ''}
              placeholder="We started at Hill Palace, took the metro north, and ended near Changampuzha Park…"
            />
            <small>
              Include place names, approximate timing, costs and local tips. Original notes are
              always preserved.
            </small>
          </label>
          {editing && (
            <fieldset className="place-checks">
              <legend>Review the places in your story</legend>
              <p className="small-copy">{editing.notice}</p>
              {places.map((p) => (
                <label key={p.id}>
                  <input
                    name="places"
                    type="checkbox"
                    value={p.id}
                    defaultChecked={editing.place_ids.includes(p.id)}
                  />
                  <span>{p.name}</span>
                  <small>{p.category}</small>
                </label>
              ))}
            </fieldset>
          )}
          {!editing && aiEnabled && (
            <label className="ai-choice">
              <input type="checkbox" name="use_ai" />
              Use Gemini to structure this story. Your notes and the public place catalog will be
              sent to Google.
            </label>
          )}
          {editing?.summary && <p className="notice">{editing.summary}</p>}
          {editing?.unresolved?.length > 0 && (
            <p className="notice">Needs your review: {editing.unresolved.join(', ')}</p>
          )}
          <ErrorNotice error={error} />
          <button className="button dark full" disabled={busy}>
            {busy ? (
              <LoaderCircle className="spin" size={17} />
            ) : editing ? (
              <CheckCircle2 size={17} />
            ) : (
              <Sparkles size={17} />
            )}{' '}
            {busy
              ? 'Saving your story…'
              : editing
                ? 'Save reviewed draft'
                : 'Save & structure my story'}
          </button>
          {editing && (
            <button
              className="button full schedule-draft"
              type="button"
              disabled={busy || !editing.place_ids.length}
              onClick={schedule}
            >
              <Footprints size={17} />
              Turn this story into a scheduled trip
              <ArrowRight size={17} />
            </button>
          )}
          <p className="small-copy form-footnote">
            {editing?.method ||
              (aiEnabled
                ? 'AI is available when you opt in; catalog matching works without it.'
                : 'Catalog matching is active. Connect a backend API key to enable optional AI extraction.')}{' '}
            Your story stays a private draft.
          </p>
        </form>
        <aside>
          <div className="writing-note">
            <span className="eyebrow">THE BEST TIPS ARE PERSONAL</span>
            <h2>
              “Go a little earlier.
              <br />
              Ask for the local special.
              <br />
              Take the longer way.”
            </h2>
            <p>These are the details that make a trip feel like a recommendation from a friend.</p>
          </div>
          <section className="draft-list">
            <div className="section-heading">
              <h2>Your drafts</h2>
              {editing && (
                <button
                  className="icon-button"
                  aria-label="Write another story"
                  onClick={() => {
                    if (!dirty || window.confirm('Discard unsaved edits and start a new story?')) {
                      setEditing(null);
                      setDirty(false);
                    }
                  }}
                >
                  <Plus size={19} />
                </button>
              )}
            </div>
            {drafts.length ? (
              drafts.map((d) => (
                <button
                  key={d.id}
                  className="draft-item"
                  onClick={() => {
                    if (!dirty || window.confirm('Discard unsaved edits and open this draft?')) {
                      setEditing(d);
                      setDirty(false);
                    }
                  }}
                >
                  <FileText size={20} />
                  <span>
                    <strong>{d.title}</strong>
                    <small>{d.place_ids.length} recognized places · Private draft</small>
                  </span>
                  <ArrowUpRight size={17} />
                </button>
              ))
            ) : (
              <p className="small-copy">Your saved stories will appear here.</p>
            )}
          </section>
        </aside>
      </div>
    </main>
  );
}

export function Profile() {
  const { me } = useApp();
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="COLLECT MOMENTS, NOT JUST MILES"
        title="Your explorer’s journal"
        subtitle="Every little step is part of a bigger story."
      />
      <section className="profile-panel">
        <span className="profile-avatar large">Y</span>
        <div>
          <h2>A curious traveler</h2>
          <p>Guest explorer · This browser’s local session</p>
        </div>
        <Link className="button" to="/create">
          <Plus size={17} />
          Share a story
        </Link>
      </section>
      <div className="stats-grid">
        <div>
          <Sparkles />
          <strong>{new Intl.NumberFormat('en-IN').format(me.points)}</strong>
          <span>Explorer points</span>
        </div>
        <div>
          <Footprints />
          <strong>{me.completed}</strong>
          <span>Stops completed</span>
        </div>
        <div>
          <MapPin />
          <strong>{me.trips.length}</strong>
          <span>Trips planned</span>
        </div>
      </div>
      <div className="section-heading">
        <div>
          <h2>Small milestones. Good memories.</h2>
          <p>Complete your itinerary to collect these badges.</p>
        </div>
      </div>
      <div className="badges-grid">
        {[
          ['First footsteps', 'Complete your first stop', Footprints],
          ['Day well spent', 'Finish every stop in a day', Leaf],
          ['Trip storyteller', 'Complete an entire itinerary', Award],
        ].map(([title, description, Icon]) => (
          <article
            key={title}
            className={`badge-card ${me.badges.includes(title) ? 'unlocked' : ''}`}
          >
            <div>
              <Icon size={35} />
            </div>
            <h3>{title}</h3>
            <p>{description}</p>
            <span>{me.badges.includes(title) ? 'Earned' : 'Still to discover'}</span>
          </article>
        ))}
      </div>
      <p className="notice">
        10 points per stop, plus 25 points per completed day. Completion is self-reported. Undoing a
        stop updates your points and badges. Guest data is tied to this browser cookie; this is not
        an authenticated profile.
      </p>
    </main>
  );
}

export function SLHGuide() {
  const { places, showSLH } = useApp();
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="A LITTLE MORE CLARITY BEFORE YOU GO"
        title="Meet the SLH score"
        subtitle="Safety. Legitimacy. Hygiene. Three perspectives, one clearer picture."
      />
      <div className="slh-guide-hero">
        <div className="large-shield">
          <ShieldCheck size={62} />
        </div>
        <div>
          <h2>Know what goes into the number.</h2>
          <p>
            SLH brings together community observations to help you compare places. It complements
            your judgment and current local information.
          </p>
          <span className="tag">Pilot scores are illustrative sample data</span>
        </div>
      </div>
      <div className="community-principles slh-principles">
        {[
          [
            ShieldCheck,
            'Safety',
            'How comfortable and accessible does the place feel? Consider lighting, surroundings and access to help.',
          ],
          [
            BadgeCheck,
            'Legitimacy',
            'Does the experience match its description? Consider transparent pricing, accurate listings and misleading claims.',
          ],
          [
            Droplets,
            'Hygiene',
            'How well is the place maintained? Consider cleanliness, food handling and shared facilities.',
          ],
        ].map(([Icon, title, text]) => (
          <div key={title}>
            <Icon />
            <h2>{title}</h2>
            <p>{text}</p>
          </div>
        ))}
      </div>
      <div className="methodology">
        <div>
          <span className="eyebrow">THE CALCULATION</span>
          <h2>Three ratings. Equal weight.</h2>
          <p>
            Each dimension is rated from 1 to 5. Add the three ratings, divide by 15 and multiply by
            100. If any dimension is missing, the place is unrated.
          </p>
        </div>
        <div className="formula">
          ( S + L + H ) ÷ 15 × 100<small>Example: (4.5 + 4.8 + 4.2) ÷ 15 × 100 = 90</small>
        </div>
      </div>
      <section>
        <div className="section-heading">
          <h2>Look beneath the score.</h2>
          <p>Select a sample rating to see its breakdown.</p>
        </div>
        <div className="slh-place-list">
          {places.map((p) => (
            <div key={p.id}>
              <span>
                <strong>{p.name}</strong>
                <small>
                  {p.category} · {p.slh.reviews} illustrative reviews
                </small>
              </span>
              <SLHPill slh={p.slh} onClick={() => showSLH(p)} />
            </div>
          ))}
        </div>
      </section>
      <p className="notice">
        SLH is not a certification or guarantee. This prototype has no live review collection or
        verified safety data. A future release should distinguish fresh evidence, review volume, and
        reports requiring investigation rather than hiding them in an average.
      </p>
    </main>
  );
}

export function Credits() {
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="WITH CREDIT, AND THANKS"
        title="The people behind the pictures"
        subtitle="Real photographs of a place worth getting to know."
      />
      <div className="credits-list">
        {[
          [
            'Chinese Fishing Nets Cochin',
            'Brian Snelson',
            '4/4f/Chinese_Fishing_Nets_Cochin.jpg',
            'Chinese_Fishing_Nets_Cochin.jpg',
            '2.0',
            'by',
          ],
          [
            'Mattancherry Palace Interior',
            'BgbwikiV4',
            'f/f7/Mattancherry_Palace_Interior.jpg',
            'Mattancherry_Palace_Interior.jpg',
            '4.0',
            'by',
          ],
          [
            'Kerala Feast or Kerala Sadya',
            'Reshmi.vm',
            '6/69/Kerala_Feast_or_Kerala_Sadya.jpg',
            'Kerala_Feast_or_Kerala_Sadya.jpg',
            '4.0',
            'by-sa',
          ],
        ].map(([title, author, , file, version, license]) => (
          <article className="form-panel" key={file}>
            <h2>{title}</h2>
            <p>
              Photograph by {author}. Displayed with layout cropping; any adapted image retains its
              applicable license.
            </p>
            <a
              href={`https://commons.wikimedia.org/wiki/File:${file}`}
              target="_blank"
              rel="noreferrer"
            >
              View original on Wikimedia Commons <ArrowUpRight size={15} />
            </a>
            <a
              href={`https://creativecommons.org/licenses/${license}/${version}/`}
              target="_blank"
              rel="noreferrer"
            >
              CC {license.toUpperCase()} {version}
            </a>
          </article>
        ))}
      </div>
      <p className="notice">
        Place descriptions, estimates, contributor identities and SLH reviews in the pilot are
        illustrative. The photos show real locations and food; they are not evidence of the sample
        creators’ visits.
      </p>
    </main>
  );
}
