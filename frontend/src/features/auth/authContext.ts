import { createContext } from "react";

import type { AuthUser } from "../../api/auth";

export interface AuthContextValue {
  user: AuthUser | null;
  csrfToken: string | null;
  isLoading: boolean;
  login: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue | null>(null);
