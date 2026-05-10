import { ApiClient } from "@brokerapp/api-client";

export type { AssetOut, BarsResponse, WatchlistOut, WatchlistDetail } from "@brokerapp/api-client";

/** Server-side client (uses the in-memory session token). */
export function serverApi(getToken: () => Promise<string | null>) {
  return new ApiClient({
    baseUrl: process.env.API_INTERNAL_URL ?? "http://api.brokerapp:8000",
    getToken,
  });
}

/** Browser-side client. The token is injected by the QueryProvider. */
export function browserApi(getToken: () => Promise<string | null>) {
  return new ApiClient({
    baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "/api/proxy",
    getToken,
  });
}
