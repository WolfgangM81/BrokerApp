"use client";

import { Plus, Trash2 } from "lucide-react";
import { useTranslations } from "next-intl";
import * as React from "react";
import { Link } from "@/i18n/routing";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  useAddMember,
  useAssetSearch,
  useDeleteWatchlist,
  useRemoveMember,
  useWatchlist,
} from "@/lib/hooks";

export function WatchlistDetailClient({ id }: { id: string }) {
  const t = useTranslations("watchlists");
  const tCommon = useTranslations("common");
  const tAssets = useTranslations("assets");
  const { data, isLoading, error } = useWatchlist(id);
  const removeMember = useRemoveMember(id);
  const addMember = useAddMember(id);
  const del = useDeleteWatchlist();
  const [search, setSearch] = React.useState("");
  const [open, setOpen] = React.useState(false);
  const results = useAssetSearch(search);

  if (isLoading) return <p className="text-sm text-neutral-500">{tCommon("loading")}</p>;
  if (error) return <p className="text-sm text-red-600">{(error as Error).message}</p>;
  if (!data) return null;

  return (
    <section className="flex flex-col gap-6">
      <header className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
          {data.description ? (
            <p className="text-sm text-neutral-500">{data.description}</p>
          ) : null}
        </div>
        <Button
          variant="destructive"
          size="sm"
          onClick={async () => {
            if (window.confirm(t("deleteConfirm"))) {
              await del.mutateAsync(data.id);
              window.location.assign("/watchlists");
            }
          }}
        >
          {tCommon("delete")}
        </Button>
      </header>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>{t("members")}</CardTitle>
            <CardDescription>{t("addMemberHint")}</CardDescription>
          </div>
          <Dialog open={open} onOpenChange={setOpen}>
            <DialogTrigger asChild>
              <Button size="sm">
                <Plus className="h-4 w-4" /> {t("addMember")}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>{t("addMember")}</DialogTitle>
              </DialogHeader>
              <Input
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder={tAssets("symbol")}
              />
              <ul className="max-h-64 overflow-y-auto">
                {results.data?.items.map((asset) => (
                  <li key={asset.id} className="flex items-center justify-between border-b py-2">
                    <div>
                      <span className="font-medium">{asset.symbol}</span>
                      <span className="ml-2 text-xs text-neutral-500">{asset.asset_class}</span>
                    </div>
                    <Button
                      size="sm"
                      onClick={async () => {
                        await addMember.mutateAsync(asset.id);
                        setOpen(false);
                      }}
                    >
                      {tCommon("create")}
                    </Button>
                  </li>
                ))}
              </ul>
              <DialogFooter>
                <Button variant="outline" onClick={() => setOpen(false)}>
                  {tCommon("cancel")}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </CardHeader>
        <CardContent>
          {data.members.length === 0 ? (
            <p className="text-sm text-neutral-500">{tCommon("empty")}</p>
          ) : (
            <ul>
              {data.members.map((m) => (
                <li key={m.asset_id} className="flex items-center justify-between border-b py-2">
                  <Link
                    href={{ pathname: "/assets/[id]", params: { id: m.asset_id } }}
                    className="font-medium underline-offset-2 hover:underline"
                  >
                    {m.asset_id.slice(0, 8)}…
                  </Link>
                  <Button
                    size="icon"
                    variant="ghost"
                    aria-label={tCommon("delete")}
                    onClick={async () => {
                      if (window.confirm(t("removeMemberConfirm"))) {
                        await removeMember.mutateAsync(m.asset_id);
                      }
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
