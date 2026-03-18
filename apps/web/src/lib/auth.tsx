/** Auth context: JWT from server OAuth, localStorage persistence, auto-expire. */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';
import type { User } from './types';

// ─── Types ──────────────────────────────────────────────────────

interface AuthContextValue {
  user: User | null;
  token: string | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: () => void;
  loginFromCallback: (jwt: string) => void;
  logout: () => void;
}

// ─── Constants ──────────────────────────────────────────────────

const TOKEN_KEY = 'repoforge_token';
const USER_KEY = 'repoforge_user';

export const API_URL = import.meta.env.VITE_API_URL ?? '';

// ─── JWT Decoder ────────────────────────────────────────────────

function decodeJwtPayload(token: string): User | null {
  try {
    const parts = token.split('.');
    const payload = parts[1];
    if (!payload) return null;
    const decoded = JSON.parse(atob(payload)) as Record<string, unknown>;

    // Check expiration
    const exp = decoded.exp as number | undefined;
    if (exp && Date.now() / 1000 > exp) {
      return null; // Token expired
    }

    return {
      github_user_id: decoded.github_user_id as number,
      login: decoded.login as string,
      avatar_url: decoded.avatar_url as string,
    };
  } catch {
    return null;
  }
}

// ─── Context ────────────────────────────────────────────────────

const AuthContext = createContext<AuthContextValue | null>(null);

// ─── Provider ───────────────────────────────────────────────────

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // Restore session from localStorage
  useEffect(() => {
    const savedToken = localStorage.getItem(TOKEN_KEY);
    if (savedToken) {
      const decoded = decodeJwtPayload(savedToken);
      if (decoded) {
        setUser(decoded);
        setToken(savedToken);
      } else {
        // Token expired or invalid — clean up
        localStorage.removeItem(TOKEN_KEY);
        localStorage.removeItem(USER_KEY);
      }
    }
    setIsLoading(false);
  }, []);

  const login = useCallback(() => {
    window.location.href = `${API_URL}/auth/login`;
  }, []);

  const loginFromCallback = useCallback((jwt: string) => {
    const decoded = decodeJwtPayload(jwt);
    if (decoded) {
      localStorage.setItem(TOKEN_KEY, jwt);
      localStorage.setItem(USER_KEY, JSON.stringify(decoded));
      setToken(jwt);
      setUser(decoded);
    }
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USER_KEY);
    setUser(null);
    setToken(null);
    window.location.hash = '#/login';
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        isLoading,
        isAuthenticated: user !== null && token !== null,
        login,
        loginFromCallback,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

// ─── Hooks ──────────────────────────────────────────────────────

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
