import { setRequestLocale } from "next-intl/server";
import { requireSession } from "@/lib/require-session";
import { AssetDetailClient } from "./asset-detail-client";

export default async function AssetDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  await requireSession();
  return <AssetDetailClient id={id} />;
}
