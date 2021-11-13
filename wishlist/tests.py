import random
from unittest.mock import Mock

import pytest

from .utils import create_hash


@pytest.mark.parametrize(
    "text, length, expected",
    [
        ("", None, "4d0c472b"),
        ("test", None, "f23b3367"),
        ("ěščřžýáí", None, "d796730e"),
        ("", 20, "4d0c472b52f09ff2d130"),
        ("test", 1, "f"),
    ],
)
def test_create_hash(text, length, expected, settings, monkeypatch):
    # prepare mocks
    random.seed(0)
    settings.SECRET_KEY = "123"
    datetime_mock = Mock()
    now_mock = Mock()
    now_mock.isoformat.return_value = "456"
    datetime_mock.now.return_value = now_mock
    monkeypatch.setattr("wishlist.utils.datetime", datetime_mock)

    if length is not None:
        res_hash = create_hash(text, length=length)
    else:
        res_hash = create_hash(text)
    assert res_hash == expected
