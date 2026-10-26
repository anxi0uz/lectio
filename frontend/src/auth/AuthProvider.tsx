import { useQueryClient } from '@tanstack/react-query';
import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react';

import { api, refreshSession, setAccessToken } from '../api/client';
import type { AuthResponse, User, UserRole } from '../api/types';

export interface RegisterData {
  email: string;
  password: string;
  first_name: string;
  last_name: string;
  role: UserRole;
}

interface AuthContextValue {
  user: User | null;
  /** False until the stored session has been checked on page load. */
  ready: boolean;
  isTeacher: boolean;
  login: (email: string, password: string) => Promise<User>;
  register: (data: RegisterData) => Promise<User>;
  logout: () => Promise<void>;
  setUser: (user: User) => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let cancelled = false;

    refreshSession()
      .then((ok) => (ok ? api<User>('/auth/me') : null))
      .catch(() => null)
      .then((me) => {
        if (cancelled) return;
        setUser(me);
        setReady(true);
      });

    const onSignedOut = () => {
      setAccessToken(null);
      setUser(null);
    };
    window.addEventListener('lectio:signed-out', onSignedOut);

    return () => {
      cancelled = true;
      window.removeEventListener('lectio:signed-out', onSignedOut);
    };
  }, []);

  const signIn = useCallback(
    (response: AuthResponse) => {
      setAccessToken(response.access_token);
      setUser(response.user);
      client.invalidateQueries();
      return response.user;
    },
    [client],
  );

  const login = useCallback(
    async (email: string, password: string) =>
      signIn(
        await api<AuthResponse>('/auth/login', {
          method: 'POST',
          body: { email, password },
        }),
      ),
    [signIn],
  );

  const register = useCallback(
    async (data: RegisterData) =>
      signIn(await api<AuthResponse>('/auth/register', { method: 'POST', body: data })),
    [signIn],
  );

  const logout = useCallback(async () => {
    await api('/auth/logout', { method: 'POST' }).catch(() => undefined);
    setAccessToken(null);
    setUser(null);
    client.clear();
  }, [client]);

  const value = useMemo(
    () => ({
      user,
      ready,
      isTeacher: user?.role === 'teacher',
      login,
      register,
      logout,
      setUser,
    }),
    [user, ready, login, register, logout],
  );

  return <AuthContext value={value}>{children}</AuthContext>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used inside AuthProvider');
  return context;
}
