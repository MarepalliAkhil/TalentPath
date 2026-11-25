import { createContext, useContext, useMemo, useState, type ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { api, ApiError } from '@/lib/api';
import type { User } from '@/lib/types';

export interface AuthValue {
  user: User | null;
  loading: boolean;
  /** True right after a deliberate logout: send people to plain /login, without a ?next= link. */
  signedOut: boolean;
  login: (email: string, password: string) => Promise<User>;
  /** Registration sends the form with the resume (multipart): full_name, email, password, accept_terms, resume. */
  register: (form: FormData) => Promise<User>;
  logout: () => Promise<void>;
}

// eslint-disable-next-line react-refresh/only-export-components -- context shared with tests
export const AuthContext = createContext<AuthValue | null>(null);

async function fetchMe(): Promise<User | null> {
  try {
    return (await api<{ user: User }>('/auth/me')).user;
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) return null;
    throw error;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const client = useQueryClient();
  const me = useQuery({ queryKey: ['me'], queryFn: fetchMe, staleTime: 60_000, retry: false });
  const [signedOut, setSignedOut] = useState(false);

  const value = useMemo<AuthValue>(
    () => ({
      user: me.data ?? null,
      loading: me.isPending,
      signedOut,
      async login(email, password) {
        const { user } = await api<{ user: User }>('/auth/login', { method: 'POST', body: { email, password } });
        setSignedOut(false);
        client.setQueryData(['me'], user);
        return user;
      },
      async register(form) {
        const { user } = await api<{ user: User }>('/auth/register', { method: 'POST', form });
        setSignedOut(false);
        client.setQueryData(['me'], user);
        return user;
      },
      async logout() {
        try {
          await api('/auth/logout', { method: 'POST' });
        } finally {
          // Sign the UI out first, then drop every other cached query.
          // (client.clear() would detach the "me" observer and leave the old user on screen.)
          setSignedOut(true);
          client.setQueryData(['me'], null);
          client.removeQueries({ predicate: (query) => query.queryKey[0] !== 'me' });
        }
      },
    }),
    [me.data, me.isPending, signedOut, client],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// eslint-disable-next-line react-refresh/only-export-components -- hook lives beside its provider
export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error('useAuth must be used inside <AuthProvider>');
  return value;
}
