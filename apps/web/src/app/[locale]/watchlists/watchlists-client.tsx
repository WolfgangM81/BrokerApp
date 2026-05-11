"use client";

import { Plus } from "lucide-react";
import { useTranslations } from "next-intl";
import * as React from "react";
import { Link } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { useCreateWatchlist, useWatchlists } from "@/lib/hooks";

export function WatchlistsClient() {
  const t = useTranslations("watchlists");
  const tCommon = useTranslations("common");
  const { data, isLoading, error } = useWatchlists();
  const create = useCreateWatchlist();
  const [open, setOpen] = React.useState(false);
  const [name, setName] = React.useState("");
  const [description, setDescription] = React.useState("");

  return (
    <section className="flex flex-col gap-6">
      <header className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{t("title")}</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button size="sm">
              <Plus className="h-4 w-4" /> {t("create")}
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>{t("createDialog.title")}</DialogTitle>
              <DialogDescription>{t("addMemberHint")}</DialogDescription>
            </DialogHeader>
            <div className="flex flex-col gap-3">
              <Input
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder={t("createDialog.namePlaceholder")}
              />
              <Input
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder={t("createDialog.descriptionPlaceholder")}
              />
            </div>
            <DialogFooter>
              <Button variant="outline" onClick={() => setOpen(false)}>
                {tCommon("cancel")}
              </Button>
              <Button
                disabled={!name.trim() || create.isPending}
                onClick={async () => {
                  await create.mutateAsync({
                    name: name.trim(),
                    description: description.trim() || undefined,
                  });
                  setName("");
                  setDescription("");
                  setOpen(false);
                }}
              >
                {tCommon("create")}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      {isLoading ? (
        <p className="text-sm text-neutral-500">{tCommon("loading")}</p>
      ) : error ? (
        <p className="text-sm text-red-600">{tCommon("error")}: {(error as Error).message}</p>
      ) : !data || data.length === 0 ? (
        <p className="rounded-md border border-dashed border-neutral-300 p-8 text-center text-sm text-neutral-500">
          {t("empty")}
        </p>
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.map((wl) => (
            <Link key={wl.id} href={`/watchlists/${wl.id}`}>
              <Card className="transition-colors hover:bg-neutral-50">
                <CardHeader>
                  <CardTitle>{wl.name}</CardTitle>
                </CardHeader>
                <CardContent className="text-sm text-neutral-500">
                  {wl.description ?? "—"}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </section>
  );
}
