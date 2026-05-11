"use client";

import { useTranslations } from "next-intl";
import * as React from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { AssetChart } from "@/components/charts/asset-chart";
import type { BarsResponse } from "@brokerapp/api-client";
import { useAsset, useBars } from "@/lib/hooks";

const GRANULARITIES: BarsResponse["granularity"][] = ["5m", "15m", "1h", "1d"];

export function AssetDetailClient({ id }: { id: string }) {
  const t = useTranslations("assets");
  const tCommon = useTranslations("common");
  const [granularity, setGranularity] = React.useState<BarsResponse["granularity"]>("1d");
  const asset = useAsset(id);
  const bars = useBars(id, granularity);

  if (asset.isLoading) return <p className="text-sm text-neutral-500">{tCommon("loading")}</p>;
  if (asset.error) return <p className="text-sm text-red-600">{(asset.error as Error).message}</p>;
  if (!asset.data) return null;

  return (
    <section className="flex flex-col gap-6">
      <header className="flex items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">
            {asset.data.symbol}{" "}
            <span className="ml-2 text-sm font-normal text-neutral-500">{asset.data.name}</span>
          </h1>
          <p className="text-xs uppercase tracking-wide text-neutral-500">
            {asset.data.asset_class} · {asset.data.exchange ?? "—"} · {asset.data.currency ?? "—"}
          </p>
        </div>
        <div className="flex gap-1 rounded-md border border-neutral-200 bg-white p-1 text-xs">
          {GRANULARITIES.map((g) => (
            <button
              key={g}
              type="button"
              onClick={() => setGranularity(g)}
              className={
                granularity === g
                  ? "rounded bg-neutral-900 px-2 py-1 font-medium text-white"
                  : "rounded px-2 py-1 text-neutral-600 hover:bg-neutral-100"
              }
            >
              {g}
            </button>
          ))}
        </div>
      </header>

      <Card>
        <CardHeader>
          <CardTitle>
            {t("granularity")}: {granularity}
          </CardTitle>
        </CardHeader>
        <CardContent className="h-[420px]">
          {bars.isLoading ? (
            <p className="text-sm text-neutral-500">{tCommon("loading")}</p>
          ) : !bars.data || bars.data.bars.length === 0 ? (
            <p className="text-sm text-neutral-500">{t("noBars")}</p>
          ) : (
            <AssetChart bars={bars.data.bars} />
          )}
        </CardContent>
      </Card>
    </section>
  );
}
