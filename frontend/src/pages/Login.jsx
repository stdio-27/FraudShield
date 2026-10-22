import { useState } from 'react';
import { Navigate, useNavigate } from 'react-router-dom';
import { AlertCircle, Loader2, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/Button';
import SystemStatus from '../components/SystemStatus';

const inputClass =
  'h-9 w-full rounded-md border bg-transparent px-3 text-sm placeholder:text-muted-foreground/60 hover:border-ring/60 focus-visible:ring-offset-0';

export default function Login() {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const { login, loading, error, isAuthenticated } = useAuth();
  const navigate = useNavigate();

  if (isAuthenticated) return <Navigate to="/dashboard" replace />;

  const handleSubmit = async (e) => {
    e.preventDefault();
    const success = await login(email.trim(), password);
    if (success) navigate('/dashboard');
  };

  return (
    <div className="flex min-h-screen flex-col">
      <header className="flex h-14 items-center justify-between px-4 sm:px-6">
        <div className="flex items-center gap-2.5">
          <div className="flex h-8 w-8 items-center justify-center rounded-md border bg-card">
            <ShieldCheck className="h-4 w-4" aria-hidden="true" />
          </div>
          <span className="text-sm font-semibold tracking-tight">FraudShield</span>
        </div>
        <SystemStatus />
      </header>

      <main className="flex flex-1 items-center justify-center px-4 pb-16">
        <div className="w-full max-w-sm">
          <div className="mb-6">
            <h1 className="text-xl font-semibold tracking-tight">Sign in</h1>
            <p className="mt-1.5 text-sm text-muted-foreground">
              Use your analyst account to access the operations console.
            </p>
          </div>

          <div className="rounded-lg border bg-card p-5">
            {error && (
              <div
                role="alert"
                className="mb-4 flex items-start gap-2 rounded-md border border-risk-high/30 bg-risk-high/5 p-3 text-xs"
              >
                <AlertCircle className="mt-px h-4 w-4 shrink-0 text-risk-high" aria-hidden="true" />
                <span>{error}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4" noValidate={false}>
              <div className="space-y-1.5">
                <label htmlFor="email" className="text-xs font-medium">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  autoComplete="username"
                  required
                  autoFocus
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                  placeholder="name@company.com"
                />
              </div>

              <div className="space-y-1.5">
                <label htmlFor="password" className="text-xs font-medium">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputClass}
                />
              </div>

              <Button type="submit" disabled={loading} className="w-full">
                {loading ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" /> Signing in…
                  </>
                ) : (
                  'Sign in'
                )}
              </Button>
            </form>
          </div>

          <p className="mt-4 text-center text-xs text-muted-foreground">
            Authorised personnel only. Accounts are created by an administrator.
          </p>
        </div>
      </main>
    </div>
  );
}
