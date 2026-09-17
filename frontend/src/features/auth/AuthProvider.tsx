import { useQueryClient } from "@tanstack/react-query";
import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";

import {
  ApiError,
  getCurrentSession,
  login as loginRequest,
  logout as logoutRequest,
  type AuthUser,
} from "../../api/auth";
import { SESSION_EXPIRED_EVENT } from "../../api/client";
import { AuthContext } from "./authContext";

export function AuthProvider({ children }: PropsWithChildren) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [csrfToken, setCsrfToken] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const controller = new AbortController();
    let active = true;
    void getCurrentSession(controller.signal)
      .then((session) => {
        if (active) {
          setUser(session.user);
          setCsrfToken(session.csrf_token);
        }
      })
      .catch((error: unknown) => {
        if (active && !(error instanceof DOMException && error.name === "AbortError")) {
          setUser(null);
          setCsrfToken(null);
        }
      })
      .finally(() => {
        if (active) setIsLoading(false);
      });
    return () => {
      active = false;
      controller.abort();
    };
  }, []);

  useEffect(() => {
    const expireSession = () => {
      setUser(null);
      setCsrfToken(null);
      queryClient.clear();
    };
    window.addEventListener(SESSION_EXPIRED_EVENT, expireSession);
    return () => window.removeEventListener(SESSION_EXPIRED_EVENT, expireSession);
  }, [queryClient]);

  const login = useCallback(async (email: string, password: string) => {
    const session = await loginRequest(email, password);
    setUser(session.user);
    setCsrfToken(session.csrf_token);
  }, []);

  const logout = useCallback(async () => {
    try {
      if (csrfToken) {
        await logoutRequest(csrfToken);
      }
    } catch (error) {
      if (!(error instanceof ApiError && error.status === 401)) {
        throw error;
      }
    }
    setUser(null);
    setCsrfToken(null);
    queryClient.clear();
  }, [csrfToken, queryClient]);

  const value = useMemo(
    () => ({ user, csrfToken, isLoading, login, logout }),
    [user, csrfToken, isLoading, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
