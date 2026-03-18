import { lazy, Suspense } from 'react';
import { HashRouter, Navigate, Route, Routes } from 'react-router-dom';
import { ErrorBoundary } from '@/components/ErrorBoundary';
import { Layout } from '@/components/Layout';
import { ProtectedRoute } from '@/components/ProtectedRoute';
import { LoadingSpinner } from '@/components/LoadingSpinner';

// ─── Lazy-loaded pages (code splitting) ─────────────────────────
const Login = lazy(() => import('@/pages/Login').then((m) => ({ default: m.Login })));
const AuthCallback = lazy(() =>
  import('@/pages/AuthCallback').then((m) => ({ default: m.AuthCallback })),
);
const Dashboard = lazy(() => import('@/pages/Dashboard').then((m) => ({ default: m.Dashboard })));
const Generate = lazy(() => import('@/pages/Generate').then((m) => ({ default: m.Generate })));
const GenerationView = lazy(() =>
  import('@/pages/GenerationView').then((m) => ({ default: m.GenerationView })),
);
const History = lazy(() => import('@/pages/History').then((m) => ({ default: m.History })));
const HistoryDetail = lazy(() =>
  import('@/pages/HistoryDetail').then((m) => ({ default: m.HistoryDetail })),
);
const Analytics = lazy(() => import('@/pages/Analytics').then((m) => ({ default: m.Analytics })));
const Settings = lazy(() => import('@/pages/Settings').then((m) => ({ default: m.Settings })));

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <ProtectedRoute>
      <Layout>{children}</Layout>
    </ProtectedRoute>
  );
}

export function App() {
  return (
    <HashRouter>
      <ErrorBoundary>
        <Suspense fallback={<LoadingSpinner />}>
          <Routes>
            {/* Public routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            {/* Protected routes */}
            <Route
              path="/"
              element={
                <ProtectedLayout>
                  <Dashboard />
                </ProtectedLayout>
              }
            />
            <Route
              path="/generate"
              element={
                <ProtectedLayout>
                  <Generate />
                </ProtectedLayout>
              }
            />
            <Route
              path="/generate/:id"
              element={
                <ProtectedLayout>
                  <GenerationView />
                </ProtectedLayout>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedLayout>
                  <History />
                </ProtectedLayout>
              }
            />
            <Route
              path="/history/:id"
              element={
                <ProtectedLayout>
                  <HistoryDetail />
                </ProtectedLayout>
              }
            />
            <Route
              path="/analytics"
              element={
                <ProtectedLayout>
                  <Analytics />
                </ProtectedLayout>
              }
            />
            <Route
              path="/settings"
              element={
                <ProtectedLayout>
                  <Settings />
                </ProtectedLayout>
              }
            />

            {/* Fallback */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </ErrorBoundary>
    </HashRouter>
  );
}
