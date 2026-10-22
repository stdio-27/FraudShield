import { NavLink } from 'react-router-dom';
import { LayoutDashboard, LogOut, ShieldAlert, ShieldCheck } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { cn } from '../lib/utils';
import { Badge } from './ui/Badge';

const navItems = [
  { to: '/dashboard', label: 'Overview', icon: LayoutDashboard },
  { to: '/alerts', label: 'Alerts queue', icon: ShieldAlert },
];

const ROLE_LABEL = { admin: 'Admin', analyst: 'Analyst', readonly: 'Read-only' };

export default function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth();
  const initials = (user?.email || '?').slice(0, 2).toUpperCase();

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="flex h-14 items-center gap-2.5 border-b px-4">
        <div className="flex h-8 w-8 items-center justify-center rounded-md border bg-card">
          <ShieldCheck className="h-4 w-4" aria-hidden="true" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold tracking-tight">FraudShield</p>
          <p className="text-2xs text-muted-foreground">Security operations</p>
        </div>
      </div>

      <nav className="flex-1 px-2 py-3" aria-label="Primary">
        <p className="px-2 pb-1.5 text-2xs font-medium uppercase tracking-wider text-muted-foreground">Monitor</p>
        <ul className="space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <li key={to}>
              <NavLink
                to={to}
                onClick={onNavigate}
                className={({ isActive }) =>
                  cn(
                    'flex items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium transition-colors',
                    isActive
                      ? 'bg-accent text-foreground'
                      : 'text-muted-foreground hover:bg-accent/60 hover:text-foreground',
                  )
                }
              >
                <Icon className="h-4 w-4" aria-hidden="true" />
                {label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <div className="border-t p-3">
        <div className="flex items-center gap-2.5 rounded-md px-1.5 py-1.5">
          <div
            className="num flex h-8 w-8 shrink-0 items-center justify-center rounded-md border bg-card text-2xs font-medium"
            aria-hidden="true"
          >
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-medium" title={user?.email || ''}>
              {user?.email || 'Signed in'}
            </p>
            {user?.role && (
              <Badge tone="outline" className="mt-1">
                {ROLE_LABEL[user.role] || user.role}
              </Badge>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={logout}
          className="mt-2 flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-sm font-medium text-muted-foreground transition-colors hover:bg-accent/60 hover:text-foreground"
        >
          <LogOut className="h-4 w-4" aria-hidden="true" />
          Sign out
        </button>
      </div>
    </div>
  );
}
