import hashlib
import random
import sys
from datetime import datetime

from django.conf import settings


def create_hash(text: str = "", length: int = 8) -> str:
    """
    Generate random letter-number hash with input text.
    """
    h = hashlib.sha1()
    data = [
        datetime.now().isoformat(),
        str(random.randint(0, sys.maxsize)),
        settings.SECRET_KEY,
        text,
    ]
    h.update(("".join(data)).encode("utf-8"))
    return h.hexdigest()[:length]
