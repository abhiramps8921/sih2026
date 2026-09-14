import { useState } from 'react';
import { Compass, MapPin, Footprints } from 'lucide-react';
import { send } from './api';

export default function Auth({ user, refresh }) {
  const [signup, setSignup] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  async function submit(event, role) {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError('');
    try {
      if (role) {
        await send('/auth/role', 'PUT', { role });
      } else {
        await send(signup ? '/auth/signup' : '/auth/login', 'POST', { email, password });
        setPassword('');
      }
      await refresh();
    } catch (err) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <main id="main" className="auth-shell">
      <section className="auth-card" aria-labelledby="auth-title">
        <span className="brand-symbol">
          <Footprints size={26} />
        </span>
        <p className="eyebrow">YOUR NEXT STORY STARTS HERE</p>
        <h1 id="auth-title">
          {user ? 'How are you exploring?' : signup ? 'Join Roam.' : 'Welcome back.'}
        </h1>
        <p>
          {user
            ? 'Are you visiting Kochi or calling it home?'
            : 'Log in to keep your trips, discoveries and memories together.'}
        </p>
        {error && (
          <p className="auth-error" role="alert">
            {error}
          </p>
        )}
        {user ? (
          <div className="auth-roles">
            <p className="auth-email">Signed in as {user.email}</p>
            <button
              className="auth-role"
              disabled={busy}
              onClick={(event) => submit(event, 'tourist')}
            >
              <Compass size={28} />
              <span>
                <strong>I’m a tourist</strong>
                <small>Discover places and plan my visit.</small>
              </span>
            </button>
            <button
              className="auth-role"
              disabled={busy}
              onClick={(event) => submit(event, 'local')}
            >
              <MapPin size={28} />
              <span>
                <strong>I’m a local</strong>
                <small>Explore my city and share local favorites.</small>
              </span>
            </button>
          </div>
        ) : (
          <form onSubmit={submit} className="auth-form">
            <label htmlFor="auth-email">Email</label>
            <input
              id="auth-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              maxLength={254}
              required
              disabled={busy}
            />
            <label htmlFor="auth-password">Password</label>
            <input
              id="auth-password"
              type="password"
              autoComplete={signup ? 'new-password' : 'current-password'}
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              minLength={8}
              maxLength={128}
              required
              disabled={busy}
              aria-describedby="password-hint"
            />
            <small id="password-hint">
              {signup
                ? 'Use 8–128 characters. Use this same password each time you log in.'
                : 'Enter the password you used when creating your account.'}
            </small>
            <button className="button dark" type="submit" disabled={busy}>
              {busy ? 'Please wait…' : signup ? 'Create account' : 'Log in'}
            </button>
            <button
              className="text-button"
              type="button"
              disabled={busy}
              onClick={() => {
                setSignup(!signup);
                setError('');
                setPassword('');
              }}
            >
              {signup ? 'Already have an account? Log in' : 'New to Roam? Create an account'}
            </button>
          </form>
        )}
        {busy && <p role="status">Saving your details…</p>}
      </section>
    </main>
  );
}
