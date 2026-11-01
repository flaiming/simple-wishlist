import secrets


def create_hash(length: int = 8) -> str:
    """
    Generate cryptographically secure random hex string of given length.
    """
    return secrets.token_hex((length + 1) // 2)[:length]
