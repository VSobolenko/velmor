#!/usr/bin/env python3
"""Replace BEPAID_PUBLIC_KEY in packages/api/.env.dev with a generated RSA PEM."""

from __future__ import annotations

import re
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ENV_PATH = Path('/opt/velmor/app/packages/api/.env.dev')


def main() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode('utf-8')
        .strip()
    )
    escaped = pem.replace('\n', '\\n')
    text = ENV_PATH.read_text(encoding='utf-8')
    replacement = f'BEPAID_PUBLIC_KEY="{escaped}"'
    if re.search(r'^BEPAID_PUBLIC_KEY=', text, flags=re.M) is None:
        raise SystemExit('BEPAID_PUBLIC_KEY missing')
    # Drop a possibly multiline quoted value, then insert one line.
    lines: list[str] = []
    skipping = False
    replaced = False
    for line in text.splitlines():
        if skipping:
            if '"' in line:
                skipping = False
            continue
        if line.startswith('BEPAID_PUBLIC_KEY='):
            lines.append(replacement)
            replaced = True
            quote_count = line.count('"')
            if quote_count == 1:
                skipping = True
            continue
        lines.append(line)
    if not replaced:
        raise SystemExit('failed to replace BEPAID_PUBLIC_KEY')
    ENV_PATH.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    ENV_PATH.chmod(0o600)
    print('updated BEPAID_PUBLIC_KEY')


if __name__ == '__main__':
    main()
