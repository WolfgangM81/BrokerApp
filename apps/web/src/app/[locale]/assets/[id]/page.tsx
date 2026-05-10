import { setRequestLocale } from "next-intl/server";
import { AssetDetailClient } from "./asset-detail-client";

export default async function AssetDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <AssetDetailClient id={id} />;
}
