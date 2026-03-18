/**
 * OAuth callback page.
 *
 * The server redirects to: `.../#/auth/callback?token=<jwt>`
 * or `.../#/auth/callback?error=<code>` on failure.
 */

import { useEffect, useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { Sparkles } from 'lucide-react';
import { useAuth } from '@/lib/auth';

const ERROR_MESSAGES: Record<string, string> = {
  state_expired: 'Your login session expired. Please try again.',
  invalid_state: 'Security validation failed. Please try again.',
  exchange_failed: 'Could not complete authentication with GitHub.',
  access_denied: 'You cancelled the authorization. Want to try again?',
  missing_code: 'Error in the GitHub response. Please try again.',
  server_error: 'Server error. Please try again later.',
};

export function AuthCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { loginFromCallback } = useAuth();

  const [status, setStatus] = useState<'loading' | 'error'>('loading');
  const [errorMessage, setErrorMessage] = useState('');

  useEffect(() => {
    const token = searchParams.get('token');
    const error = searchParams.get('error');

    // Clean the token from the URL immediately
    window.history.replaceState(
      null,
      '',
      `${window.location.pathname + window.location.search}#/auth/callback`,
    );

    if (token) {
      loginFromCallback(token);
      navigate('/', { replace: true });
    } else if (error) {
      setStatus('error');
      setErrorMessage(ERROR_MESSAGES[error] ?? `Authentication error: ${error}`);
    } else {
      navigate('/login', { replace: true });
    }
  }, [loginFromCallback, navigate, searchParams]);

  if (status === 'loading') {
    return (
      <div className="flex min-h-screen items-center justify-center bg-surface-bg px-4">
        <div className="w-full max-w-md text-center">
          <Sparkles className="mx-auto mb-4 h-16 w-16 text-primary-400" />
          <div className="flex items-center justify-center gap-3">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary-600 border-t-transparent" />
            <p className="text-lg text-text-secondary">Signing you in...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-surface-bg px-4">
      <div className="w-full max-w-md">
        <div className="mb-8 text-center">
          <Sparkles className="mx-auto mb-4 h-16 w-16 text-primary-400" />
          <h1 className="text-3xl font-bold text-text-primary">RepoForge</h1>
        </div>

        <div className="rounded-lg border border-surface-border bg-surface-card p-6">
          <div className="mb-4 rounded-lg border border-red-500/25 bg-red-500/10 px-4 py-3 text-sm text-red-400">
            {errorMessage}
          </div>

          <Link to="/login" className="btn-primary flex w-full items-center justify-center gap-2">
            Try Again
          </Link>
        </div>
      </div>
    </div>
  );
}
