export function PurchaseComplete() {
  return (
    <div className="min-h-screen bg-bg font-sans text-text antialiased">
      <div className="mx-auto flex max-w-[480px] flex-col items-center gap-3 px-6 pt-[15vh] text-center">
        <div className="w-full rounded-xl border border-border bg-panel p-7 shadow-sm">
          <h1 className="text-xl font-semibold text-heading">Thanks for your purchase</h1>
          <p className="mt-3 text-sm text-text/75">
            Your license key is on its way to your email. Add it to your deployment's{" "}
            <code className="rounded bg-accent-soft px-1 py-0.5 font-mono text-xs text-heading">.env</code> as{" "}
            <code className="rounded bg-accent-soft px-1 py-0.5 font-mono text-xs text-heading">LICENSE_KEY</code>{" "}
            (with{" "}
            <code className="rounded bg-accent-soft px-1 py-0.5 font-mono text-xs text-heading">
              LICENSE_REQUIRED=true
            </code>
            ) to unlock the full product.
          </p>
          <p className="mt-3 text-sm text-text/75">
            Don't see the email in a minute or two? Check spam, or contact support with the email
            address you paid with.
          </p>
          <a
            className="mt-5 inline-block rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent/90"
            href="/"
          >
            Back to the app
          </a>
        </div>
      </div>
    </div>
  );
}
