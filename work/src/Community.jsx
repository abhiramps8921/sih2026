import { useEffect, useState } from 'react';
import { Check, Clock, MapPin, Plus, Users } from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { api, send } from './api';
import { useApp } from './context';
import { ErrorNotice, PageHeading } from './components';
import { interests } from './data';

const DEMO_GROUPS = [
  {
    id: 'sunrise',
    title: 'A slow morning in Fort Kochi',
    date: '2026-10-03',
    time: '09:00',
    place: 'Chinese Fishing Nets',
    capacity: 6,
    members: 3,
    tags: ['Photography', 'Easy pace'],
    host: 'Ananya',
    initials: 'AM',
    status: false,
  },
  {
    id: 'food-walk',
    title: 'Good food, better company',
    date: '2026-10-04',
    time: '12:00',
    place: 'Mattancherry Palace entrance',
    capacity: 6,
    members: 4,
    tags: ['Food', 'Culture'],
    host: 'Meera',
    initials: 'MK',
    status: false,
  },
];

export default function Community() {
  const [params, setParams] = useSearchParams();
  const creating = params.get('action') === 'create';
  const [groups, setGroups] = useState([]);
  const [demoGroups, setDemoGroups] = useState(DEMO_GROUPS);
  const [nextOffset, setNextOffset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [itinerary, setItinerary] = useState('');
  const { me, notify } = useApp();
  function mode(action) {
    const next = new URLSearchParams(params);
    next.set('action', action);
    setParams(next);
  }
  async function load(offset = 0) {
    const data = await api(`/groups?offset=${offset}`);
    setGroups((previous) => (offset ? [...previous, ...data.groups] : data.groups));
    setNextOffset(data.next_offset);
  }
  useEffect(() => {
    let active = true;
    api('/groups')
      .then((data) => {
        if (active) {
          setGroups(data.groups);
          setNextOffset(data.next_offset);
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
  }, []);
  async function mutate(path, method, data, message) {
    setBusy(true);
    setError('');
    try {
      await send(path, method, data);
      try {
        await load();
      } catch (e) {
        setError(`Your change was saved, but the list could not refresh: ${e.message}`);
      }
      notify(message);
      return true;
    } catch (e) {
      setError(e.message);
      // A competing join may have filled a group since this page was loaded.
      try {
        await load();
      } catch {
        /* Keep the original actionable error. */
      }
      return false;
    } finally {
      setBusy(false);
    }
  }
  async function create(e) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const saved = await mutate(
      '/groups',
      'POST',
      {
        name: form.get('name'),
        date: form.get('date'),
        meeting_point: form.get('meeting_point'),
        capacity: Number(form.get('capacity')),
        interests: form.getAll('interests'),
        itinerary_id: itinerary || null,
        share_itinerary: form.get('share_itinerary') === 'on',
      },
      'Group created. You are its owner and first member.',
    );
    if (saved) {
      setItinerary('');
      mode('join');
    }
  }
  function toggleDemoGroup(id) {
    setDemoGroups((previous) =>
      previous.map((group) => (group.id === id ? { ...group, status: !group.status } : group)),
    );
    const group = demoGroups.find((candidate) => candidate.id === id);
    notify(
      group.status
        ? 'Demo request withdrawn.'
        : 'Demo request saved. No real person was contacted.',
    );
  }
  return (
    <main id="main" className="main-shell">
      <PageHeading
        eyebrow="SOME STORIES ARE BETTER SHARED"
        title="Find your kind of people"
        subtitle="Create a group or join travelers with shared interests in Kochi."
      />
      <div className="interest-row" aria-label="Group actions">
        <button
          className={`interest ${creating ? 'selected' : ''}`}
          aria-pressed={creating}
          onClick={() => mode('create')}
        >
          Create group
        </button>
        <button
          className={`interest ${!creating ? 'selected' : ''}`}
          aria-pressed={!creating}
          onClick={() => mode('join')}
        >
          Join group
        </button>
      </div>
      <ErrorNotice error={error} />
      {creating ? (
        <form className="form-panel group-form" onSubmit={create}>
          <h2>Create group</h2>
          <p className="field-hint">
            Group details are visible to signed-in travelers. Choose a public meeting point, not a
            home or stay address.
          </p>
          <fieldset disabled={busy} className="tag-fieldset">
            <label className="field">
              Group name
              <input name="name" required minLength={3} maxLength={100} />
            </label>
            <div className="form-grid">
              <label className="field">
                Date
                <input name="date" type="date" required max="2100-12-31" />
              </label>
              <label className="field">
                Capacity, including you
                <input name="capacity" type="number" min={2} max={50} defaultValue={6} required />
              </label>
            </div>
            <label className="field">
              Public meeting point
              <input
                name="meeting_point"
                required
                minLength={3}
                maxLength={200}
                placeholder="For example, Mattancherry Palace entrance"
              />
            </label>
            <fieldset className="tag-fieldset">
              <legend>Interests · choose at least one</legend>
              <div className="tag-options">
                {interests
                  .filter((x) => x !== 'All experiences')
                  .map((interest) => (
                    <label className="interest" key={interest}>
                      <input type="checkbox" name="interests" value={interest} /> {interest}
                    </label>
                  ))}
              </div>
            </fieldset>
            <label className="field">
              Linked itinerary (optional)
              <select value={itinerary} onChange={(e) => setItinerary(e.target.value)}>
                <option value="">No itinerary shared</option>
                {me.trips.map((trip) => (
                  <option key={trip.id} value={trip.id}>
                    {trip.title}
                  </option>
                ))}
              </select>
            </label>
            {itinerary && (
              <div className="notice">
                <strong>Public preview: {me.trips.find((t) => t.id === itinerary)?.title}</strong>
                {me.trips
                  .find((t) => t.id === itinerary)
                  ?.days.map((day, i) => (
                    <p key={i}>
                      Day {i + 1}: {day.stops.map((s) => s.place.name).join(' → ')}
                    </p>
                  ))}
                <label>
                  <input key={itinerary} name="share_itinerary" type="checkbox" required /> Share
                  this title and these stop names with signed-in travelers. This is a fixed
                  snapshot.
                </label>
              </div>
            )}
            <button className="button dark" disabled={busy}>
              {busy ? 'Creating…' : 'Create group'}
            </button>
          </fieldset>
        </form>
      ) : (
        <>
          <div className="section-heading">
            <div>
              <h2>A few good people, a little adventure.</h2>
              <p>Sample group trips in Kochi · No live matching</p>
            </div>
          </div>
          <div className="community-grid">
            {demoGroups.map((group, index) => (
              <article className="group-card" key={group.id}>
                <img
                  src={index ? '/images/heritage.jpg' : '/images/kochi.jpg'}
                  alt={index ? 'Mattancherry Palace interior' : 'Kochi waterfront'}
                  width="750"
                  height="400"
                  loading="lazy"
                />
                <div className="group-body">
                  <div className="card-meta">
                    <span className="tag">Sample departure</span>
                    <span>
                      <Users size={14} />
                      {group.members} / {group.capacity} sample spots
                    </span>
                  </div>
                  <h2>{group.title}</h2>
                  <div className="group-facts">
                    <span>
                      <Clock size={16} />
                      {new Intl.DateTimeFormat('en-IN', {
                        day: 'numeric',
                        month: 'long',
                      }).format(new Date(`${group.date}T12:00:00`))}{' '}
                      · {group.time}
                    </span>
                    <span>
                      <MapPin size={16} />
                      {group.place}
                    </span>
                  </div>
                  <div className="tag-options">
                    {group.tags.map((tag) => (
                      <span key={tag} className="tag">
                        {tag}
                      </span>
                    ))}
                  </div>
                  <div className="group-host">
                    <span className="avatar">{group.initials}</span>
                    <span>
                      Hosted by {group.host}
                      <small>Sample profile</small>
                    </span>
                    <button
                      className={`button ${group.status ? '' : 'dark'}`}
                      onClick={() => toggleDemoGroup(group.id)}
                      disabled={busy}
                    >
                      {group.status ? <Check size={16} /> : <Plus size={16} />}{' '}
                      {group.status ? 'Withdraw request' : 'Try join request'}
                    </button>
                  </div>
                  {group.status && (
                    <p className="small-copy">
                      Demo request pending. There is no live host approval or chat.
                    </p>
                  )}
                </div>
              </article>
            ))}
          </div>
          {loading ? (
            <p role="status">Loading groups…</p>
          ) : groups.length ? (
            <>
              <div className="section-heading">
                <h2>Available groups & your memberships</h2>
              </div>
              <div className="community-grid">
                {groups.map((g) => (
                  <article className="group-card" key={g.id}>
                    <div className="group-body">
                      <div className="card-meta">
                        <span className="tag">
                          {g.closed
                            ? 'Closed'
                            : g.is_owner
                              ? 'Your group'
                              : g.joined
                                ? 'Joined'
                                : 'Open group'}
                        </span>
                        <span>
                          {g.members} / {g.capacity} members · {g.remaining} spots left
                        </span>
                      </div>
                      <h2>{g.name}</h2>
                      <p>
                        {g.date} · {g.meeting_point}
                      </p>
                      <div className="tag-options">
                        {g.interests.map((t) => (
                          <span className="tag" key={t}>
                            {t}
                          </span>
                        ))}
                      </div>
                      {g.shared_itinerary && (
                        <details>
                          <summary>Shared itinerary: {g.shared_itinerary.title}</summary>
                          {g.shared_itinerary.days.map((d, i) => (
                            <p key={i}>
                              Day {i + 1}: {d.stops.join(' → ')}
                            </p>
                          ))}
                        </details>
                      )}
                      <div className="tag-options group-actions">
                        {g.is_owner && !g.closed ? (
                          <button
                            className="button"
                            disabled={busy}
                            onClick={() =>
                              mutate(
                                `/groups/${g.id}/close`,
                                'POST',
                                {},
                                'Group closed to new joins.',
                              )
                            }
                          >
                            Close group
                          </button>
                        ) : g.joined ? (
                          <button
                            className="button"
                            disabled={busy}
                            onClick={() =>
                              mutate(
                                `/groups/${g.id}/membership`,
                                'DELETE',
                                {},
                                'You left the group.',
                              )
                            }
                          >
                            Leave group
                          </button>
                        ) : (
                          <button
                            className="button dark"
                            disabled={busy || g.closed || !g.remaining}
                            onClick={() =>
                              mutate(
                                `/groups/${g.id}/membership`,
                                'PUT',
                                {},
                                'You joined the group.',
                              )
                            }
                          >
                            {g.closed ? 'Closed' : !g.remaining ? 'Full' : 'Join group'}
                          </button>
                        )}
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </>
          ) : null}
          {nextOffset !== null && (
            <button
              className="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError('');
                try {
                  await load(nextOffset);
                } catch (e) {
                  setError(e.message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              More groups
            </button>
          )}
        </>
      )}
    </main>
  );
}
