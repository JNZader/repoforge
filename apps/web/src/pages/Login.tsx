/** Login page — GitHub OAuth button, dark gradient background. */

import { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { Github, Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';

export function Login() {
  const { isAuthenticated, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = (location.state as { from?: { pathname: string } })?.from?.pathname || '/';

  // Redirect when already authenticated
  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [isAuthenticated, from, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-bg px-4">
      <div className="w-full max-w-md">
        {/* Branding */}
        <div className="mb-8 text-center">
          <Sparkles className="mx-auto mb-4 h-16 w-16 text-primary-400" />
          <h1 className="text-3xl font-bold tracking-tight text-text-primary">RepoForge</h1>
          <p className="mt-2 text-text-secondary">
            AI Documentation & Skills Generator
          </p>
        </div>

        {/* Login Card */}
        <div className="rounded-lg border border-surface-border bg-surface-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-text-primary">Sign in with GitHub</h2>
          <p className="mb-6 text-sm text-text-secondary">
            Authenticate with your GitHub account to generate documentation and AI agent skills for
            your repositories.
          </p>

          <button
            type="button"
            onClick={login}
            className="btn-primary flex w-full items-center justify-center gap-2"
          >
            <Github className="h-5 w-5" />
            Sign in with GitHub
          </button>

          <p className="mt-4 text-center text-xs text-text-muted">
            Free & open source — bring your own API keys.
          </p>
        </div>
      </div>
    </div>
  );
}
