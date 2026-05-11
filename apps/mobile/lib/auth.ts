import * as AuthSession from "expo-auth-session";
import Constants from "expo-constants";
import * as SecureStore from "expo-secure-store";
import { useCallback, useEffect, useState } from "react";

const TOKEN_KEY = "brokerapp.access_token";
const REFRESH_KEY = "brokerapp.refresh_token";

const issuer =
  (Constants.expoConfig?.extra as { authIssuer?: string } | undefined)?.authIssuer ?? "";
const clientId =
  (Constants.expoConfig?.extra as { authClientId?: string } | undefined)?.authClientId ?? "";

const discovery = {
  authorizationEndpoint: `${issuer}authorize/`,
  tokenEndpoint: `${issuer}token/`,
  revocationEndpoint: `${issuer}revoke/`,
};

export interface AuthState {
  accessToken: string | null;
  loading: boolean;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

export function useAuth(): AuthState {
  const [accessToken, setAccessToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const redirectUri = AuthSession.makeRedirectUri({ scheme: "brokerapp", path: "auth/callback" });
  const [request, response, promptAsync] = AuthSession.useAuthRequest(
    {
      clientId,
      scopes: ["openid", "email", "profile", "groups", "offline_access"],
      usePKCE: true,
      redirectUri,
    },
    discovery,
  );

  useEffect(() => {
    SecureStore.getItemAsync(TOKEN_KEY).then((token) => {
      setAccessToken(token);
      setLoading(false);
    });
  }, []);

  useEffect(() => {
    if (response?.type !== "success" || !request) return;
    const code = response.params.code;
    AuthSession.exchangeCodeAsync(
      {
        clientId,
        code,
        redirectUri,
        extraParams: { code_verifier: request.codeVerifier ?? "" },
      },
      discovery,
    )
      .then(async (token) => {
        await SecureStore.setItemAsync(TOKEN_KEY, token.accessToken);
        if (token.refreshToken) {
          await SecureStore.setItemAsync(REFRESH_KEY, token.refreshToken);
        }
        setAccessToken(token.accessToken);
      })
      .catch(() => {
        setAccessToken(null);
      });
  }, [response, request, redirectUri]);

  const signIn = useCallback(async () => {
    await promptAsync();
  }, [promptAsync]);

  const signOut = useCallback(async () => {
    await SecureStore.deleteItemAsync(TOKEN_KEY);
    await SecureStore.deleteItemAsync(REFRESH_KEY);
    setAccessToken(null);
  }, []);

  return { accessToken, loading, signIn, signOut };
}
