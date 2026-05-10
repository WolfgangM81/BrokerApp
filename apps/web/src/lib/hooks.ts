"use client";

import { ApiClient, type AssetOut, type BarsResponse, type WatchlistDetail, type WatchlistOut } from "@brokerapp/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useSession } from "next-auth/react";
import * as React from "react";

function useApi(): ApiClient {
  const { data: session } = useSession();
  return React.useMemo(
    () =>
      new ApiClient({
        baseUrl: process.env.NEXT_PUBLIC_API_URL ?? "/api/proxy",
        getToken: () => session?.accessToken ?? null,
      }),
    [session?.accessToken],
  );
}

export function useWatchlists() {
  const api = useApi();
  return useQuery<WatchlistOut[]>({
    queryKey: ["watchlists"],
    queryFn: () => api.listWatchlists(),
  });
}

export function useWatchlist(id: string | null) {
  const api = useApi();
  return useQuery<WatchlistDetail>({
    queryKey: ["watchlists", id],
    queryFn: () => api.getWatchlist(id!),
    enabled: Boolean(id),
  });
}

export function useCreateWatchlist() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; description?: string }) => api.createWatchlist(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
}

export function useDeleteWatchlist() {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteWatchlist(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists"] }),
  });
}

export function useAddMember(watchlistId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => api.addWatchlistMember(watchlistId, { asset_id: assetId }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["watchlists", watchlistId] });
      qc.invalidateQueries({ queryKey: ["watchlists"] });
    },
  });
}

export function useRemoveMember(watchlistId: string) {
  const api = useApi();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (assetId: string) => api.removeWatchlistMember(watchlistId, assetId),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["watchlists", watchlistId] }),
  });
}

export function useAsset(id: string | null) {
  const api = useApi();
  return useQuery<AssetOut>({
    queryKey: ["assets", id],
    queryFn: () => api.getAsset(id!),
    enabled: Boolean(id),
  });
}

export function useAssetSearch(q: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["assets", "search", q],
    queryFn: () => api.listAssets({ q, limit: 20 }),
    enabled: q.length >= 1,
    staleTime: 5_000,
  });
}

export function useBars(assetId: string | null, granularity: BarsResponse["granularity"]) {
  const api = useApi();
  return useQuery<BarsResponse>({
    queryKey: ["bars", assetId, granularity],
    queryFn: () => api.getBars(assetId!, { granularity, limit: 1000 }),
    enabled: Boolean(assetId),
  });
}
