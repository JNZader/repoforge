import { useState, type ReactNode } from 'react';
import { NavLink, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  Sparkles,
  History,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
  BookOpen,
  Home,
} from 'lucide-react';
import { useAuth } from '@/lib/auth';
import { cn } from '@/lib/utils';

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
}

const navItems: NavItem[] = [
  { to: '/', label: 'Dashboard', icon: <LayoutDashboard className="h-5 w-5" />, end: true },
  { to: '/generate', label: 'Generate', icon: <Sparkles className="h-5 w-5" /> },
  { to: '/history', label: 'History', icon: <History className="h-5 w-5" /> },
  { to: '/analytics', label: 'Analytics', icon: <BarChart3 className="h-5 w-5" /> },
  { to: '/settings', label: 'Settings', icon: <Settings className="h-5 w-5" /> },
];

export function Layout({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const sidebar = (
    <>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 border-b border-surface-border px-6">
        <Sparkles className="h-7 w-7 text-primary-400" />
        <div>
          <h1 className="text-lg font-bold tracking-tight text-text-primary">RepoForge</h1>
          <p className="text-xs text-text-secondary">AI Docs & Skills</p>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={() => setSidebarOpen(false)}
            className={({ isActive }) =>
              cn(
                'flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-primary-600/15 text-primary-400'
                  : 'text-text-secondary hover:bg-surface-hover hover:text-text-primary',
              )
            }
          >
            {item.icon}
            {item.label}
          </NavLink>
        ))}

        {/* External links */}
        <div className="mt-4 border-t border-surface-border pt-4 space-y-1">
          <a
            href="/repoforge/"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
          >
            <Home className="h-5 w-5" />
            Home
          </a>
          <a
            href="/repoforge/docs/"
            className="flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-text-secondary hover:bg-surface-hover hover:text-text-primary transition-colors"
          >
            <BookOpen className="h-5 w-5" />
            Documentation
          </a>
        </div>
      </nav>

      {/* User section */}
      {user && (
        <div className="border-t border-surface-border p-4">
          <div className="flex items-center gap-3">
            <img
              src={user.avatar_url}
              alt={user.login}
              className="h-8 w-8 rounded-full"
            />
            <div className="flex-1 truncate">
              <p className="truncate text-sm font-medium text-text-primary">{user.login}</p>
            </div>
            <button
              type="button"
              onClick={handleLogout}
              className="rounded-md p-1.5 text-text-muted transition-colors hover:bg-surface-hover hover:text-text-secondary"
              title="Logout"
            >
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );

  return (
    <div className="flex h-screen overflow-hidden bg-surface-bg">
      {/* Desktop sidebar */}
      <aside className="hidden w-64 flex-col border-r border-surface-border bg-surface-card md:flex">
        {sidebar}
      </aside>

      {/* Mobile overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r border-surface-border bg-surface-card transition-transform duration-200 md:hidden',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        {sidebar}
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile top bar */}
        <header className="flex h-14 items-center gap-4 border-b border-surface-border bg-surface-card px-4 md:hidden">
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className="rounded-md p-1.5 text-text-secondary hover:bg-surface-hover"
          >
            {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary-400" />
            <span className="font-semibold text-text-primary">RepoForge</span>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto">
          <div className="p-6">{children}</div>
        </main>
      </div>
    </div>
  );
}
