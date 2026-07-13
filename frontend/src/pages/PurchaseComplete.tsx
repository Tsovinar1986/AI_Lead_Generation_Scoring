export function PurchaseComplete() {
  return (
    <div className="app">
      <div className="panel purchase-complete">
        <h1>Thanks for your purchase</h1>
        <p className="muted">
          Your license key is on its way to your email. Add it to your deployment's{" "}
          <code>.env</code> as <code>LICENSE_KEY</code> (with <code>LICENSE_REQUIRED=true</code>)
          to unlock the full product.
        </p>
        <p className="muted">
          Don't see the email in a minute or two? Check spam, or contact support with the email
          address you paid with.
        </p>
        <a className="button-link primary" href="/">
          Back to the app
        </a>
      </div>
    </div>
  );
}
