#!/usr/bin/env python3
"""Run ONCE, by the seller, to create the signing keypair for this product.

    python generate_keypair.py

Prints a private key (put it in the SELLER's .env as LICENSE_PRIVATE_KEY --
this is what issue_license.py uses to sign purchased licenses; never commit
it, never send it to anyone) and a public key (put it in
backend/app/config.py's LICENSE_PUBLIC_KEY default, or ship it as an env var
with the product -- it only verifies signatures, it's safe for every buyer
to have a copy of it).

Re-running this script invalidates every license key issued so far, since
they were signed with the old private key. Do it once and keep the private
key backed up somewhere safe.
"""

import base64

from nacl.signing import SigningKey


def main() -> None:
    signing_key = SigningKey.generate()
    private_b64 = base64.urlsafe_b64encode(bytes(signing_key)).decode().rstrip("=")
    public_b64 = base64.urlsafe_b64encode(bytes(signing_key.verify_key)).decode().rstrip("=")

    print("LICENSE_PRIVATE_KEY (seller .env only -- keep secret):")
    print(f"  {private_b64}\n")
    print("LICENSE_PUBLIC_KEY (bake into the shipped product, safe to commit):")
    print(f"  {public_b64}")


if __name__ == "__main__":
    main()
