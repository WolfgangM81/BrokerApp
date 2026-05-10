import { setRequestLocale } from "next-intl/server";
import { WatchlistDetailClient } from "./watchlist-detail-client";

export default async function WatchlistDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  return <WatchlistDetailClient id={id} />;
}
