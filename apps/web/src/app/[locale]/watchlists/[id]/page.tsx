import { setRequestLocale } from "next-intl/server";
import { requireSession } from "@/lib/require-session";
import { WatchlistDetailClient } from "./watchlist-detail-client";

export default async function WatchlistDetailPage({
  params,
}: {
  params: Promise<{ locale: string; id: string }>;
}) {
  const { locale, id } = await params;
  setRequestLocale(locale);
  await requireSession();
  return <WatchlistDetailClient id={id} />;
}
