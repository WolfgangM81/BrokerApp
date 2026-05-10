"use client";

import { signIn } from "next-auth/react";
import { useSearchParams } from "next/navigation";

export default function SignInPage() {
  const params = useSearchParams();
  const callbackUrl = params.get("callbackUrl") ?? "/";
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6 bg-neutral-50 px-6">
      <div className="w-full max-w-sm rounded-lg border border-neutral-200 bg-white p-8 shadow-sm">
        <h1 className="mb-2 text-xl font-semibold tracking-tight">BrokerApp</h1>
        <p className="mb-6 text-sm text-neutral-500">
          Anmeldung über Authentik. Diese App ist intern und nicht öffentlich erreichbar.
        </p>
        <button
          type="button"
          onClick={() => signIn("authentik", { callbackUrl })}
          className="w-full rounded-md bg-neutral-900 px-4 py-2 text-sm font-medium text-white hover:bg-neutral-800"
        >
          Mit Authentik anmelden
        </button>
      </div>
    </main>
  );
}
