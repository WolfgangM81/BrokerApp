import { getTranslations, setRequestLocale } from "next-intl/server";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Link } from "@/i18n/routing";
import { requireSession } from "@/lib/require-session";

export default async function DashboardPage({
  params,
}: {
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;
  setRequestLocale(locale);
  const t = await getTranslations("dashboard");
  const session = await requireSession();

  return (
    <section className="flex flex-col gap-6">
      <header className="flex flex-col gap-1">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <p className="text-sm text-neutral-500">
          {t("welcome", { name: session.user?.name ?? session.user?.email ?? "—" })}
        </p>
      </header>
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>{t("openWatchlists")}</CardTitle>
          </CardHeader>
          <CardContent>
            <Link href="/watchlists" className="text-sm font-medium underline">
              →
            </Link>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("trackedAssets")}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-neutral-500">—</CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>{t("recentForecasts")}</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-neutral-500">
            Phase 3 ⏳
          </CardContent>
        </Card>
      </div>
    </section>
  );
}
