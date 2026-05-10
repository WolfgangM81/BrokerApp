"use client";

import { ChevronDown, LogOut } from "lucide-react";
import { useTranslations } from "next-intl";
import { signOut, useSession } from "next-auth/react";
import { Link, usePathname } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { LocaleSwitch } from "@/components/locale-switch";

export function SiteHeader() {
  const t = useTranslations("nav");
  const pathname = usePathname();
  const { data: session, status } = useSession();

  const tabs: { href: "/" | "/watchlists"; label: string }[] = [
    { href: "/", label: t("dashboard") },
    { href: "/watchlists", label: t("watchlists") },
  ];

  return (
    <header className="border-b border-neutral-200 bg-white">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-6 px-4">
        <Link href="/" className="text-base font-semibold tracking-tight">
          BrokerApp
        </Link>
        <nav className="flex items-center gap-3 text-sm">
          {tabs.map((tab) => {
            const active = pathname === tab.href;
            return (
              <Link
                key={tab.href}
                href={tab.href}
                className={
                  active
                    ? "text-neutral-900"
                    : "text-neutral-500 transition-colors hover:text-neutral-900"
                }
              >
                {tab.label}
              </Link>
            );
          })}
        </nav>
        <div className="ml-auto flex items-center gap-2">
          <LocaleSwitch />
          {status === "authenticated" && session?.user ? (
            <div className="flex items-center gap-2">
              <span className="hidden text-xs text-neutral-500 sm:inline">
                {session.user.email}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => signOut({ callbackUrl: "/auth/signin" })}
                aria-label={t("signOut")}
              >
                <LogOut className="h-4 w-4" />
              </Button>
            </div>
          ) : (
            <Button asChild size="sm" variant="outline">
              <Link href="/auth/signin">
                {t("signIn")}
                <ChevronDown className="ml-1 h-4 w-4" />
              </Link>
            </Button>
          )}
        </div>
      </div>
    </header>
  );
}
