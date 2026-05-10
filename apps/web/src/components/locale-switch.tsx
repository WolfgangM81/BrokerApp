"use client";

import { useLocale, useTranslations } from "next-intl";
import { usePathname, useRouter } from "@/i18n/routing";
import { Button } from "@/components/ui/button";

const ALT: Record<string, "de" | "en"> = { de: "en", en: "de" };

export function LocaleSwitch() {
  const t = useTranslations("nav");
  const locale = useLocale();
  const router = useRouter();
  const pathname = usePathname();
  const next = ALT[locale] ?? "de";
  return (
    <Button
      size="sm"
      variant="ghost"
      onClick={() => router.replace(pathname, { locale: next })}
      aria-label={t("language")}
    >
      {next.toUpperCase()}
    </Button>
  );
}
