import { AlertTriangle } from "lucide-react";
import { useTranslations } from "next-intl";

export function Disclaimer() {
  const t = useTranslations("app");
  return (
    <div className="flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
      <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>{t("disclaimer")}</span>
    </div>
  );
}
