import { useState, useEffect } from 'react';
import { Link, NavLink, Routes, Route, useLocation } from 'react-router-dom';
import { Compass, Map, Users, Plus, Footprints, LoaderCircle, Sparkles } from 'lucide-react';
import Explore from './Explore';
import Auth from './Auth';
import { api, send } from './api';
import { AppContext } from './context';
import { SLHDetails } from './components';
import { Planner, Itinerary, MyTrips, ActiveTrip } from './Trips';
import Community from './Community';
import { CreateTrip, Profile, SLHGuide, Credits } from './Pages';
import { usePlannerTool } from './webmcp';
export default function App() {
  usePlannerTool();
  const [me, setMe] = useState({ saved: [], trips: [], points: 0, badges: [], completed: 0 });
  const [places, setPlaces] = useState([]);
  const [regions, setRegions] = useState([]);
  const [status, setStatus] = useState('loading');
  const [error, setError] = useState('');
  const [toast, setToast] = useState('');
  const [slhPlace, setSlhPlace] = useState(null);
  const [bookmarkBusy, setBookmarkBusy] = useState(false);
  const [logoutBusy, setLogoutBusy] = useState(false);
  const location = useLocation();
  const plannerParams = new URLSearchParams();
  if (
    location.pathname === '/' ||
    location.pathname.startsWith('/itinerary/') ||
    location.pathname === '/plan'
  ) {
    const exploreParams = new URLSearchParams(location.search);
    for (const key of ['area', 'interest', 'pace', 'travel_type']) {
      if (exploreParams.get(key)) plannerParams.set(key, exploreParams.get(key));
    }
  }
  const plannerHref = plannerParams.size ? `/plan?${plannerParams}` : '/plan';
  async function refresh() {
    const profile = await api('/me');
    setMe(profile);
    return profile;
  }
  async function load() {
    setStatus('loading');
    setError('');
    try {
      const [, loadedPlaces, loadedRegions] = await Promise.all([
        refresh(),
        api('/places'),
        api('/regions'),
      ]);
      setPlaces(loadedPlaces);
      setRegions(loadedRegions);
      setStatus('ready');
    } catch (e) {
      setError(e.message);
      setStatus('error');
    }
  }
  useEffect(() => {
    load();
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' });
  }, [location.pathname]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(''), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  async function toggleSave(id) {
    if (bookmarkBusy) return;
    setBookmarkBusy(true);
    try {
      const saved = !me.saved.includes(id);
      await send(`/bookmarks/${id}`, 'PUT', { saved });
      await refresh();
      setToast(saved ? 'Saved to your collection.' : 'Removed from your collection.');
    } catch (e) {
      setToast(e.message);
    } finally {
      setBookmarkBusy(false);
    }
  }
  async function logout() {
    setLogoutBusy(true);
    try {
      await send('/auth/logout', 'POST', {});
      setSlhPlace(null);
      await load();
    } catch (e) {
      setToast(e.message);
    } finally {
      setLogoutBusy(false);
    }
  }
  return (
    <AppContext.Provider
      value={{
        me,
        places,
        regions,
        refresh,
        toggleSave,
        bookmarkBusy,
        notify: setToast,
        showSLH: setSlhPlace,
        plannerHref,
      }}
    >
      <a className="skip-link" href="#main">
        Skip to content
      </a>
      <header className="site-header">
        <div className="nav-shell">
          <Link className="brand" to="/" aria-label="Roam home">
            <span className="brand-symbol">
              <Footprints size={22} />
            </span>
            roam<span className="brand-dot">.</span>
          </Link>
          {me.user?.role_selected && (
            <nav aria-label="Main navigation">
              <NavLink to="/" end>
                <Compass size={18} />
                Explore
              </NavLink>
              <NavLink to={plannerHref}>
                <Sparkles size={18} />
                Plan a trip
              </NavLink>
              <NavLink to="/trips">
                <Map size={18} />
                My trips
              </NavLink>
              <NavLink to="/community">
                <Users size={18} />
                Community
              </NavLink>
            </nav>
          )}
          <div className="header-actions">
            {me.user?.role_selected && (
              <Link className="text-button share-link" to="/create">
                <Plus size={17} />
                Share a trip
              </Link>
            )}
            {me.user?.role_selected && (
              <Link className="profile-avatar" to="/profile" aria-label="Your profile">
                Y
              </Link>
            )}
            {me.user && (
              <button className="text-button" onClick={logout} disabled={logoutBusy}>
                {logoutBusy ? 'Logging out…' : 'Log out'}
              </button>
            )}
          </div>
        </div>
      </header>
      {status === 'loading' ? (
        <main className="main-shell" id="main">
          <div className="loading-state">
            <LoaderCircle className="spin" />
            <h2>Finding your next story…</h2>
          </div>
        </main>
      ) : status === 'error' ? (
        <main className="main-shell" id="main">
          <div className="empty-state">
            <h1>Let’s reconnect.</h1>
            <p role="alert">{error}</p>
            <button className="button dark" onClick={load}>
              Retry connection
            </button>
          </div>
        </main>
      ) : !me.user || !me.user.role_selected ? (
        <Auth user={me.user} refresh={refresh} />
      ) : (
        <Routes>
          <Route path="/" element={<Explore />} />
          <Route path="/plan" element={<Planner />} />
          <Route path="/itinerary/:id" element={<Itinerary />} />
          <Route path="/trips" element={<MyTrips />} />
          <Route path="/trips/:id" element={<ActiveTrip />} />
          <Route path="/community" element={<Community />} />
          <Route path="/create" element={<CreateTrip />} />
          <Route path="/profile" element={<Profile />} />
          <Route path="/slh" element={<SLHGuide />} />
          <Route path="/credits" element={<Credits />} />
          <Route
            path="*"
            element={
              <main className="main-shell" id="main">
                <div className="empty-state">
                  <h1>A little off the trail.</h1>
                  <Link to="/" className="button dark">
                    Back to Explore
                  </Link>
                </div>
              </main>
            }
          />
        </Routes>
      )}
      {slhPlace && <SLHDetails place={slhPlace} close={() => setSlhPlace(null)} />}
      <div className="toast-region" role="status" aria-live="polite">
        {toast && <div className="toast">{toast}</div>}
      </div>
    </AppContext.Provider>
  );
}
