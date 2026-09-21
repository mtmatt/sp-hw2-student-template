"""Decryption for encryptor.c's sealed-box scheme.

encryptor.c seals `data` for its selected server public key using X25519-via-Ed25519 ECDH
(ed25519/key_exchange.c: an Edwards public key converted to its Montgomery
u-coordinate, then a standard X25519 scalar multiplication) followed by
ChaCha20. This module reimplements only the decrypt direction, using
`cryptography` for the elliptic-curve and stream-cipher primitives — the
Edwards->Montgomery conversion has no library equivalent, so it's done by
hand per the formula `key_exchange.c` cites (CodesInChaos:
montgomeryX = (edwardsY + 1) * inverse(1 - edwardsY) mod p).

See encryptor/encryptor.c (print_encrypted, derive_key_nonce) and
encryptor/tests/decrypt_check.c (the reference decrypt implementation) for
the construction this mirrors.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

# 2^255 - 19: the field prime Curve25519/Ed25519 are defined over (the same
# constant encryptor/ed25519/fe.c's field-element arithmetic reduces
# against). Both the Edwards->Montgomery conversion below and X25519 itself
# operate on coordinates mod this prime.
_P = 2**255 - 19


class DecryptError(Exception):
    """Raised when a sealed-box blob can't be decoded or decrypted."""


@dataclass(frozen=True)
class ServerKeys:
    """The judge's half of the encryptor keypair, loaded from a keys dir."""

    public_key: bytes  # 32 bytes, Edwards form (encryptor.c's server public key)
    private_scalar: bytes  # low 32 bytes of the 64-byte private_key= value

    @classmethod
    def load(cls, keys_dir: str | Path) -> ServerKeys:
        keys_dir = Path(keys_dir)
        public_key = bytes.fromhex((keys_dir / "server_public_key.hex").read_text().strip())
        if len(public_key) != 32:
            raise ValueError(
                f"server_public_key.hex must decode to 32 bytes, got {len(public_key)}"
            )

        # server_secret_key.hex holds `key=value` lines -- `seed=...` (the
        # 32-byte seed the pair was generated from) and `private_key=...`
        # (the 64-byte expanded secret key ed25519_key_exchange needs; see
        # encryptor/keys/gen_server_keys.c and encryptor/keys/README.md,
        # which produce and document this same file format). We only need
        # the latter, so scan for its line and ignore the rest.
        private_key_hex = None
        for line in (keys_dir / "server_secret_key.hex").read_text().splitlines():
            if line.startswith("private_key="):
                private_key_hex = line[len("private_key=") :].strip()
                break
        if private_key_hex is None:
            raise ValueError("server_secret_key.hex is missing a private_key= line")

        private_key = bytes.fromhex(private_key_hex)
        if len(private_key) != 64:
            raise ValueError(f"private_key= must decode to 64 bytes, got {len(private_key)}")

        return cls(public_key=public_key, private_scalar=private_key[:32])


def _edwards_y_to_montgomery_u(edwards_public_key: bytes) -> bytes:
    """Convert a 32-byte Edwards25519 public key to its Montgomery u-coordinate."""
    y = int.from_bytes(edwards_public_key, "little") & ((1 << 255) - 1)
    u = ((1 + y) * pow((1 - y) % _P, -1, _P)) % _P
    return u.to_bytes(32, "little")


def decrypt(server_keys: ServerKeys, blob: bytes) -> bytes:
    """Decrypt an `epk(32 bytes) || ciphertext` blob.

    `blob` is exactly what `encryptor` prints hex-encoded after its `Ok: `
    prefix -- e.g. given encryptor's stdout line `Ok: <hex>`, the caller
    hex-decodes `<hex>` (the part after `Ok: `) into `blob` before calling
    this (or just calls `decrypt_hex` directly with `<hex>` as a string).
    This function never sees the `Ok: ` prefix itself.

    Doesn't need the original token/sid: decryption only depends on the
    blob itself and the server's own keys (see decrypt_check.c).
    """
    if len(blob) < 32:
        raise DecryptError("blob too short to contain a 32-byte ephemeral public key")

    epk, ciphertext = blob[:32], blob[32:]

    try:
        # y == 1 mod p makes (1 - y) non-invertible; both this and the
        # exchange() call below can raise ValueError on attacker-controlled
        # epk bytes (epk arrives straight off the FIFO, never validated
        # against a real encryptor run), so both must convert to DecryptError.
        montgomery_pub = _edwards_y_to_montgomery_u(epk)
        shared = X25519PrivateKey.from_private_bytes(server_keys.private_scalar).exchange(
            X25519PublicKey.from_public_bytes(montgomery_pub)
        )
    except ValueError as e:
        raise DecryptError(f"invalid ephemeral public key: {e}") from e

    derived = hashlib.sha512(shared + epk + server_keys.public_key).digest()
    key, nonce = derived[:32], derived[32:44]

    cipher = Cipher(algorithms.ChaCha20(key, b"\x00\x00\x00\x00" + nonce), mode=None)
    return cipher.decryptor().update(ciphertext)


def decrypt_hex(server_keys: ServerKeys, hex_blob: str) -> bytes:
    """Like `decrypt`, but takes the hex-encoded blob as encryptor emits it."""
    try:
        blob = bytes.fromhex(hex_blob)
    except ValueError as e:
        raise DecryptError(f"not valid hex: {e}") from e
    return decrypt(server_keys, blob)
