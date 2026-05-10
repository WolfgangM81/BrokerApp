export default function Home() {
  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col items-start justify-center gap-6 px-6 py-16">
      <span className="rounded-full bg-amber-100 px-3 py-1 text-xs font-medium uppercase tracking-wider text-amber-900">
        Phase 0 · Foundation
      </span>
      <h1 className="text-4xl font-semibold tracking-tight">BrokerApp</h1>
      <p className="text-lg text-neutral-700">
        ML-powered stock forecast and decision-support tool. The repo skeleton is in place;
        nothing is shipped yet.
      </p>
      <p className="rounded-md border border-neutral-200 bg-white px-4 py-3 text-sm text-neutral-600">
        Disclaimer: Not investment advice. Forecasts come with uncertainty — models can and
        will be wrong.
      </p>
    </main>
  );
}
