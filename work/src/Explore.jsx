import { Link, useSearchParams } from 'react-router-dom';
import {
  Compass,
  Bookmark,
  ArrowUpRight,
  ArrowRight,
  MapPin,
  Search,
  SlidersHorizontal,
  ShieldCheck,
  Sparkles,
  Leaf,
  Utensils,
  Landmark,
  Palette,
  Heart,
} from 'lucide-react';
import { templates, interests, money, slhScore, templateSLH } from './data';
import { useApp } from './context';
import { SLHPill } from './components';

const categoryIcons = [Compass, Utensils, Landmark, Leaf, Palette, Sparkles];
export default function Explore() {
  const [params, setParams] = useSearchParams();
  const active = params.get('interest') || 'All experiences';
  const query = params.get('q') || '';
  const { me, places, showSLH, toggleSave, bookmarkBusy } = useApp();
  const saved = me.saved;
  const collection = templates.map((t) => ({
    ...t,
    slh: slhScore(templateSLH(t, places)),
    ratings: templateSLH(t, places),
  }));
  const visible = collection.filter(
    (t) =>
      (!params.has('slh') || t.slh >= 90) &&
      (active === 'All experiences' || t.tags.includes(active) || t.category === active) &&
      `${t.title} ${t.tags.join(' ')}`.toLowerCase().includes(query.toLowerCase()),
  );
  const update = (key, value) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    setParams(next, { replace: true });
  };
  return (
    <main id="main" className="main-shell">
      <div className="page-heading">
        <div>
          <div className="eyebrow">
            <span className="tiny-line" /> GO SOMEWHERE. FEEL AT HOME.
          </div>
          <h1>
            Your next story starts here<span>.</span>
          </h1>
          <p>Good places. Real people. A little more local.</p>
        </div>
        <Link to="/plan" className="button dark">
          <Sparkles size={18} />
          Build my trip
          <ArrowUpRight size={17} />
        </Link>
      </div>
      <section className="search-bar" aria-label="Search experiences">
        <div className="destination-control">
          <MapPin size={20} />
          <span>
            <small>YOUR DESTINATION</small>
            <strong>Kochi, Kerala</strong>
          </span>
          <span className="pilot-pill">Pilot city</span>
        </div>
        <div className="search-input">
          <Search size={20} />
          <input
            aria-label="Search trips"
            name="q"
            autoComplete="off"
            placeholder="Find your kind of adventure…"
            value={query}
            onChange={(e) => update('q', e.target.value)}
          />
        </div>
        <button
          className="filter-button"
          onClick={() => update('slh', params.has('slh') ? '' : '90')}
          aria-pressed={params.has('slh')}
        >
          <SlidersHorizontal size={17} />
          {params.has('slh') ? 'SLH 90+' : 'Filters'}
        </button>
      </section>
      <div className="interest-row" aria-label="Filter by interest">
        {interests.map((interest, i) => {
          const Icon = categoryIcons[i];
          return (
            <button
              key={interest}
              className={`interest ${active === interest ? 'selected' : ''}`}
              aria-pressed={active === interest}
              onClick={() => update('interest', interest === 'All experiences' ? '' : interest)}
            >
              <Icon size={17} />
              {interest}
            </button>
          );
        })}
      </div>
      <div className="explore-grid">
        <div className="explore-content">
          <section className="feature-banner">
            <img
              src="/images/kochi.jpg"
              alt="Chinese fishing nets on the Kochi waterfront at sunset"
              width="2048"
              height="1365"
              fetchPriority="high"
            />
            <div className="feature-overlay" />
            <div className="feature-content">
              <span className="glass-label">
                <MapPin size={13} />
                THE QUEEN OF THE ARABIAN SEA
              </span>
              <h2>
                Kochi, through
                <br />a local’s eyes.
              </h2>
              <p>Take the streets less scrolled.</p>
              <Link className="button white" to="/itinerary/slow-kochi">
                Explore the local favourite
                <ArrowUpRight size={17} />
              </Link>
            </div>
            <div className="banner-caption">
              <span className="stacked-avatars">
                <i>AM</i>
                <i>AR</i>
                <i>MK</i>
              </span>
              <span>
                Made with local knowledge
                <br />
                <strong>Kochi pilot collection</strong>
              </span>
            </div>
            <span className="photo-location">Fort Kochi, Kerala ↗</span>
          </section>
          <section className="trip-section">
            <div className="section-heading">
              <div>
                <h2>Worth taking the long way.</h2>
                <p>Thoughtful itineraries, inspired by people who know the place.</p>
              </div>
              <span className="collection-label">
                THE LOCAL EDIT <ArrowUpRight size={16} />
              </span>
            </div>
            <div className="trip-grid">
              {visible.map((t) => (
                <article className="trip-card" key={t.id}>
                  <div className="card-photo">
                    <Link to={`/itinerary/${t.id}`} tabIndex={-1} aria-hidden="true">
                      <img
                        src={t.image}
                        alt=""
                        width="600"
                        height="400"
                        loading="lazy"
                        onError={(e) => {
                          e.currentTarget.src = '/images/kochi.jpg';
                        }}
                      />
                    </Link>
                    <span className="image-tag">{t.category}</span>
                    <button
                      className={`save-button ${saved.includes(t.id) ? 'saved' : ''}`}
                      aria-label={`${saved.includes(t.id) ? 'Unsave' : 'Save'} ${t.title}`}
                      disabled={bookmarkBusy}
                      onClick={() => toggleSave(t.id)}
                    >
                      <Bookmark size={18} fill={saved.includes(t.id) ? 'currentColor' : 'none'} />
                    </button>
                  </div>
                  <div className="card-content">
                    <div className="card-meta">
                      <span>
                        <MapPin size={13} />
                        Kochi, Kerala
                      </span>
                      <SLHPill
                        slh={t.ratings}
                        onClick={() => showSLH({ name: t.title, slh: t.ratings })}
                      />
                    </div>
                    <h3>
                      <Link to={`/itinerary/${t.id}`}>{t.title}</Link>
                    </h3>
                    <p>{t.subtitle}</p>
                    <div className="trip-facts">
                      <span>
                        {t.days} {t.days === 1 ? 'day' : 'days'}
                      </span>
                      <i />
                      <span>From {money(t.cost)} / person</span>
                    </div>
                    <div className="creator-row">
                      <span className="avatar" style={{ background: t.color }}>
                        {t.initials}
                      </span>
                      <span>
                        <strong>{t.creator}</strong>
                        <small>{t.role} · Sample creator</small>
                      </span>
                      <ArrowUpRight size={18} />
                    </div>
                  </div>
                </article>
              ))}
            </div>
            {visible.length === 0 && (
              <div className="empty-state">
                <Search />
                <h3>No trips found</h3>
                <p>Try a different interest or search term.</p>
                <button className="button" onClick={() => setParams({})}>
                  Clear filters
                </button>
              </div>
            )}
          </section>
        </div>
        <aside className="explore-sidebar">
          <section className="planner-promo">
            <span className="sparkle-box">
              <Sparkles size={24} />
            </span>
            <span className="eyebrow">A TRIP THAT FEELS LIKE YOU</span>
            <h2>
              Your interests.
              <br />
              Your pace.
              <br />
              <em>Your kind of trip.</em>
            </h2>
            <p>A day-by-day plan with local finds, good food, and room to wander.</p>
            <Link to="/plan" className="button dark">
              Let’s plan something
              <ArrowRight size={17} />
            </Link>
            <span className="fine-print">1–3 days · Made for your budget</span>
          </section>
          <section className="slh-promo">
            <div className="slh-icon">
              <ShieldCheck size={21} />
            </div>
            <h3>A little more peace of mind.</h3>
            <p>
              Meet the <strong>SLH score.</strong> Three perspectives to help you choose your next
              stop.
            </p>
            <div className="slh-dimensions">
              <span>
                <ShieldCheck size={15} />
                Safety
              </span>
              <span>
                <Heart size={15} />
                Legitimacy
              </span>
              <span>
                <Leaf size={15} />
                Hygiene
              </span>
            </div>
            <Link to="/slh">
              Understand the score
              <ArrowUpRight size={16} />
            </Link>
          </section>
          <div className="local-note">
            <Leaf size={20} />
            <p>
              Explore thoughtfully.
              <br />
              <strong>Leave a place better than you found it.</strong>
            </p>
          </div>
        </aside>
      </div>
      <footer>
        <Link className="brand" to="/">
          roam.
        </Link>
        <p>Made for the curious. Rooted in the local.</p>
        <Link to="/credits">Photo credits</Link>
        <span>Kochi pilot · Sample content</span>
      </footer>
    </main>
  );
}
