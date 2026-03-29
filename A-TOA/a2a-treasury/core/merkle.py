"""
Merkle Tree utility for ACF session audit verification.
Computes a binary Merkle root from a list of SHA-256 hash strings.
Layer: Verification Layer — Agentic Commerce Framework

Examples
--------
>>> compute_merkle_root([])[:16]
'e3b0c44298fc1c14'

>>> h = "abc123"
>>> compute_merkle_root([h]) == h
True

>>> import hashlib
>>> a, b = "aa" * 32, "bb" * 32
>>> expected = hashlib.sha256(bytes.fromhex(a) + bytes.fromhex(b)).hexdigest()
>>> compute_merkle_root([a, b]) == expected
True
"""
from __future__ import annotations

import hashlib
from typing import Optional


def compute_merkle_root(hashes: list[str]) -> str:
    """Compute a binary Merkle root from a list of SHA-256 hex-hash strings.

    - Empty list  → sha256(b"empty").hexdigest()
    - Single hash → return as-is
    - Otherwise   → pair adjacent hashes, duplicate last on odd count,
                     recurse until one root remains
    """
    if not hashes:
        return hashlib.sha256(b"empty").hexdigest()
    if len(hashes) == 1:
        return hashes[0]

    # Work with bytes for efficiency
    level: list[bytes] = [bytes.fromhex(h) for h in hashes]

    while len(level) > 1:
        next_level: list[bytes] = []
        # Duplicate last if odd
        if len(level) % 2 == 1:
            level.append(level[-1])
        for i in range(0, len(level), 2):
            combined = hashlib.sha256(level[i] + level[i + 1]).digest()
            next_level.append(combined)
        level = next_level

    return level[0].hex()


def verify_merkle_proof(leaf_hash: str, proof: list[dict], root: str) -> bool:
    """Verify a Merkle proof for a given leaf hash against the root.

    Each proof item: {"hash": "<hex>", "position": "left" | "right"}

    >>> a, b = "aa" * 32, "bb" * 32
    >>> root = compute_merkle_root([a, b])
    >>> proof = generate_merkle_proof([a, b], a)
    >>> verify_merkle_proof(a, proof, root)
    True
    """
    current = bytes.fromhex(leaf_hash)
    for item in proof:
        sibling = bytes.fromhex(item["hash"])
        if item["position"] == "left":
            current = hashlib.sha256(sibling + current).digest()
        else:
            current = hashlib.sha256(current + sibling).digest()
    return current.hex() == root


def generate_merkle_proof(hashes: list[str], target_hash: str) -> Optional[list[dict]]:
    """Generate a Merkle proof path for a specific leaf hash.

    Returns None if target_hash is not in hashes.

    >>> a, b, c = "aa" * 32, "bb" * 32, "cc" * 32
    >>> proof = generate_merkle_proof([a, b, c], a)
    >>> proof is not None
    True
    >>> root = compute_merkle_root([a, b, c])
    >>> verify_merkle_proof(a, proof, root)
    True
    """
    if target_hash not in hashes:
        return None

    if len(hashes) == 1:
        return []  # Leaf is root, no proof needed

    target_index = hashes.index(target_hash)
    proof: list[dict] = []
    level: list[str] = list(hashes)

    idx = target_index
    while len(level) > 1:
        # Duplicate last if odd
        if len(level) % 2 == 1:
            level.append(level[-1])

        if idx % 2 == 0:
            # Target is left child, sibling is right
            sibling_hash = level[idx + 1]
            proof.append({"hash": sibling_hash, "position": "right"})
        else:
            # Target is right child, sibling is left
            sibling_hash = level[idx - 1]
            proof.append({"hash": sibling_hash, "position": "left"})

        # Build next level
        next_level: list[str] = []
        for i in range(0, len(level), 2):
            combined = hashlib.sha256(
                bytes.fromhex(level[i]) + bytes.fromhex(level[i + 1])
            ).hexdigest()
            next_level.append(combined)
        level = next_level
        idx = idx // 2

    return proof


class MerkleTree:
    """Convenience wrapper around Merkle utility functions.

    >>> tree = MerkleTree(["aa" * 32, "bb" * 32])
    >>> len(tree.get_root()) == 64
    True
    >>> tree.verify("aa" * 32, tree.get_proof("aa" * 32))
    True
    """

    def __init__(self, hashes: list[str]):
        self.leaves = list(hashes)
        self.root = compute_merkle_root(hashes)

    def get_root(self) -> str:
        return self.root

    def get_proof(self, leaf_hash: str) -> Optional[list[dict]]:
        return generate_merkle_proof(self.leaves, leaf_hash)

    def verify(self, leaf_hash: str, proof: list[dict]) -> bool:
        return verify_merkle_proof(leaf_hash, proof, self.root)

    def to_dict(self) -> dict:
        return {
            "root": self.root,
            "leaf_count": len(self.leaves),
            "leaves": self.leaves,
        }
