/**
 * Hand-written request helpers around the generated `schema.ts` types.
 *
 * Keep this file thin: one helper per endpoint, returning typed data or
 * throwing `ApiError`. Cross-cutting concerns (auth, retries, telemetry)
 * live in the consuming app's QueryProvider.
 */

import type {
  AssetCreate,
  AssetOut,
  BacktestOut,
  BarsResponse,
  BarGranularity,
  ForecastHorizon,
  ForecastOut,
  ForecastRunResponse,
  PageOfAssetOut,
  ProblemDetail,
  WatchlistCreate,
  WatchlistDetail,
  WatchlistMemberAdd,
  WatchlistOut,
  WatchlistUpdate,
} from "./schema";

export * from "./schema";

export interface ApiClientOptions {
  baseUrl: string;
  /** Resolves to a JWT bearer token, or null when unauthenticated. */
  getToken?: () => Promise<string | null> | string | null;
  /** Optional fetch override for testing. */
  fetchImpl?: typeof fetch;
}

export class ApiError extends Error {
  readonly status: number;
  readonly problem: ProblemDetail;

  constructor(problem: ProblemDetail) {
    super(problem.detail ?? problem.title);
    this.status = problem.status;
    this.problem = problem;
    this.name = "ApiError";
  }
}

interface RequestInitWithJson extends RequestInit {
  json?: unknown;
  query?: Record<string, string | number | boolean | undefined | null>;
}

export class ApiClient {
  constructor(private readonly opts: ApiClientOptions) {}

  private async request<T>(path: string, init: RequestInitWithJson = {}): Promise<T> {
    const fetchImpl = this.opts.fetchImpl ?? fetch;
    const url = new URL(path.replace(/^\//, ""), this.opts.baseUrl.replace(/\/?$/, "/"));
    if (init.query) {
      for (const [k, v] of Object.entries(init.query)) {
        if (v === undefined || v === null) continue;
        url.searchParams.set(k, String(v));
      }
    }
    const headers = new Headers(init.headers ?? {});
    headers.set("accept", "application/json");
    if (init.json !== undefined) {
      headers.set("content-type", "application/json");
    }
    const token = this.opts.getToken ? await this.opts.getToken() : null;
    if (token) headers.set("authorization", `Bearer ${token}`);
    const res = await fetchImpl(url, {
      ...init,
      headers,
      body: init.json !== undefined ? JSON.stringify(init.json) : (init.body as BodyInit | null | undefined),
    });
    if (res.status === 204) return undefined as T;
    const ctype = res.headers.get("content-type") ?? "";
    if (!res.ok) {
      let problem: ProblemDetail;
      if (ctype.includes("application/problem+json") || ctype.includes("application/json")) {
        problem = (await res.json()) as ProblemDetail;
      } else {
        problem = {
          type: "about:blank",
          title: res.statusText || "Request failed",
          status: res.status,
          code: `http.${res.status}`,
        };
      }
      throw new ApiError(problem);
    }
    return ctype.includes("application/json") ? ((await res.json()) as T) : (undefined as T);
  }

  // --- assets -------------------------------------------------------------

  listAssets(params: { q?: string; asset_class?: string; cursor?: string | null; limit?: number } = {}) {
    return this.request<PageOfAssetOut>("/v1/assets", { query: params });
  }

  getAsset(id: string) {
    return this.request<AssetOut>(`/v1/assets/${id}`);
  }

  createAsset(payload: AssetCreate) {
    return this.request<AssetOut>("/v1/assets", { method: "POST", json: payload });
  }

  // --- bars ---------------------------------------------------------------

  getBars(
    assetId: string,
    params: { granularity?: BarGranularity; from?: string; to?: string; limit?: number } = {},
  ) {
    return this.request<BarsResponse>(`/v1/assets/${assetId}/bars`, {
      query: {
        granularity: params.granularity,
        from: params.from,
        to: params.to,
        limit: params.limit,
      },
    });
  }

  // --- watchlists ---------------------------------------------------------

  listWatchlists() {
    return this.request<WatchlistOut[]>("/v1/watchlists");
  }

  createWatchlist(payload: WatchlistCreate) {
    return this.request<WatchlistOut>("/v1/watchlists", { method: "POST", json: payload });
  }

  getWatchlist(id: string) {
    return this.request<WatchlistDetail>(`/v1/watchlists/${id}`);
  }

  updateWatchlist(id: string, payload: WatchlistUpdate) {
    return this.request<WatchlistOut>(`/v1/watchlists/${id}`, { method: "PATCH", json: payload });
  }

  deleteWatchlist(id: string) {
    return this.request<void>(`/v1/watchlists/${id}`, { method: "DELETE" });
  }

  addWatchlistMember(watchlistId: string, payload: WatchlistMemberAdd) {
    return this.request<WatchlistDetail>(`/v1/watchlists/${watchlistId}/members`, {
      method: "POST",
      json: payload,
    });
  }

  removeWatchlistMember(watchlistId: string, assetId: string) {
    return this.request<void>(`/v1/watchlists/${watchlistId}/members/${assetId}`, {
      method: "DELETE",
    });
  }

  // --- forecasts / backtests ---------------------------------------------

  listForecasts(assetId: string, params: { horizon?: ForecastHorizon; limit?: number } = {}) {
    return this.request<ForecastOut[]>(`/v1/assets/${assetId}/forecasts`, { query: params });
  }

  listBacktests(assetId: string, params: { limit?: number } = {}) {
    return this.request<BacktestOut[]>(`/v1/assets/${assetId}/backtests`, { query: params });
  }

  runForecast(assetId: string, model = "lightgbm") {
    return this.request<ForecastRunResponse>(`/v1/assets/${assetId}/forecasts/run`, {
      method: "POST",
      query: { model },
    });
  }
}
