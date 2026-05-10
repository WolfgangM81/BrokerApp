import { ApiClient } from "@brokerapp/api-client";
import Constants from "expo-constants";

export function makeApiClient(getToken: () => Promise<string | null> | string | null): ApiClient {
  const baseUrl =
    (Constants.expoConfig?.extra as { apiBaseUrl?: string } | undefined)?.apiBaseUrl ??
    "http://localhost:8000";
  return new ApiClient({ baseUrl, getToken });
}
