import { setRequestLocale } from "next-intl/server";
import { WatchlistsClient } from "./watchlists-client";

export default async function WatchlistsPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  return <WatchlistsClient />;
}
