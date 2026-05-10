"use client";

import { useSearchParams } from "next/navigation";

export default function AuthErrorPage() {
  const params = useSearchParams();
  const error = params.get("error") ?? "Unknown";
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-4 px-6">
      <h1 className="text-xl font-semibold">Authentication error</h1>
      <p className="text-sm text-neutral-600">{error}</p>
      <a className="text-sm underline" href="/auth/signin">
        Back to sign-in
      </a>
    </main>
  );
}
