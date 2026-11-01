import json
import re

import pytest
from django.test import Client
from django.urls import reverse

from .models import Wish, WishList
from .utils import create_hash


@pytest.mark.parametrize("length", [1, 7, 8, 24])
def test_create_hash(length):
    value = create_hash(length)
    assert len(value) == length
    assert re.fullmatch(r"[0-9a-f]+", value)
    assert create_hash(length) != value or length == 1


# ---------- fixtures ----------


@pytest.fixture
def wishlist(db):
    wl = WishList.objects.create(name="Pepa")
    Wish.objects.create(wishlist=wl, wish="Kolo")
    Wish.objects.create(wishlist=wl, wish="Ponožky", multiple_reservation=True)
    return wl


@pytest.fixture
def owner(wishlist):
    client = Client()
    client.get(wishlist.get_absolute_url(), {"edit_slug": wishlist.edit_slug})
    return client


@pytest.fixture
def stranger(db):
    return Client()


def formset_data(wishlist, name="Pepa", wishes=None):
    wishes = wishes if wishes is not None else [(w.id, w.wish) for w in wishlist.wishes.all()]
    data = {
        "name": name,
        "description": "",
        "email": "",
        "wishes-TOTAL_FORMS": str(len(wishes)),
        "wishes-INITIAL_FORMS": str(len([w for w in wishes if w[0]])),
        "wishes-MIN_NUM_FORMS": "1",
        "wishes-MAX_NUM_FORMS": "1000",
    }
    for i, (wish_id, text) in enumerate(wishes):
        data[f"wishes-{i}-id"] = str(wish_id or "")
        data[f"wishes-{i}-wish"] = text
        data[f"wishes-{i}-position"] = str(i + 1)
    return data


def put(client, wishlist, wish_id, secret=""):
    return client.put(
        wishlist.get_absolute_url(),
        json.dumps({"wish_id": wish_id, "secret": secret}),
        content_type="application/json",
    )


# ---------- slugs ----------


def test_slugs_are_generated(wishlist):
    assert len(wishlist.slug) == 8
    assert len(wishlist.edit_slug) == 24
    assert wishlist.slug != wishlist.edit_slug[:8]


# ---------- create / edit permissions ----------


def test_create_wishlist(stranger, db):
    data = formset_data(None, name="Nový", wishes=[(None, "Kniha")])
    response = stranger.post(reverse("wishlist-create"), data)
    wl = WishList.objects.get(name="Nový")
    assert response.status_code == 302
    assert response["Location"] == f"{wl.get_absolute_url()}?edit_slug={wl.edit_slug}"
    assert list(wl.wishes.values_list("wish", flat=True)) == ["Kniha"]


def test_owner_can_edit(owner, wishlist):
    wish = wishlist.wishes.first()
    response = owner.post(wishlist.get_absolute_url(), formset_data(wishlist, name="Josef", wishes=[(wish.id, "Auto")]))
    assert response.status_code == 302
    wishlist.refresh_from_db()
    assert wishlist.name == "Josef"
    assert list(wishlist.wishes.values_list("wish", flat=True)) == ["Auto"]


def test_stranger_cannot_edit(stranger, wishlist):
    wish = wishlist.wishes.first()
    response = stranger.post(wishlist.get_absolute_url(), formset_data(wishlist, name="HACKED", wishes=[(wish.id, "x")]))
    assert response.status_code == 403
    assert wishlist.edit_slug not in response.content.decode()
    wishlist.refresh_from_db()
    assert wishlist.name == "Pepa"
    assert wishlist.wishes.count() == 2


@pytest.mark.parametrize("action", ["delete", "reset_reservations", "forget"])
def test_stranger_cannot_run_actions(stranger, wishlist, action):
    wishlist.wishes.update(reserved_count=1)
    response = stranger.post(wishlist.get_absolute_url(), {action: "doit"})
    assert response.status_code == 403
    assert WishList.objects.filter(pk=wishlist.pk).exists()
    assert wishlist.reserved_count == 2


def test_owner_can_delete(owner, wishlist):
    response = owner.post(wishlist.get_absolute_url(), {"delete": "doit"})
    assert response.status_code == 302
    assert not WishList.objects.filter(pk=wishlist.pk).exists()


def test_owner_can_reset_reservations(owner, wishlist):
    wishlist.wishes.update(reserved_count=3)
    owner.post(wishlist.get_absolute_url(), {"reset_reservations": "doit"})
    assert wishlist.reserved_count == 0


def test_wrong_edit_slug_does_not_grant_access(stranger, wishlist):
    stranger.get(wishlist.get_absolute_url(), {"edit_slug": "wrong"})
    response = stranger.post(wishlist.get_absolute_url(), {"delete": "doit"})
    assert response.status_code == 403


def test_missing_wishlist_returns_404(stranger, db):
    url = reverse("wishlist-detail", args=["neexistuje"])
    assert stranger.get(url).status_code == 404
    assert stranger.post(url, {"delete": "doit"}).status_code == 404


# ---------- rendering ----------


def test_wish_text_is_escaped(owner, stranger, wishlist):
    payload = "<img src=x onerror=alert(1)//"
    wish = wishlist.wishes.first()
    owner.post(wishlist.get_absolute_url(), formset_data(wishlist, wishes=[(wish.id, payload)]))
    html = stranger.get(wishlist.get_absolute_url()).content.decode()
    assert "<img src=x" not in html
    assert "&lt;img src=x onerror=alert(1)//" in html


def test_wish_highlighted():
    assert Wish(wish="Kniha - <b>Babička</b>").wish_highlighted == "<strong>Kniha</strong> - &lt;b&gt;Babička&lt;/b&gt;"
    assert Wish(wish="<i>Kolo</i>").wish_highlighted == "&lt;i&gt;Kolo&lt;/i&gt;"
    assert Wish(wish="").wish_highlighted == ""


def test_wish_with_link_is_urlized(stranger, wishlist):
    Wish.objects.create(wishlist=wishlist, wish="Lego - https://example.com/?a=1&b=2")
    html = stranger.get(wishlist.get_absolute_url()).content.decode()
    assert "<strong>Lego</strong>" in html
    assert 'href="https://example.com/?a=1&amp;b=2"' in html


# ---------- reservations ----------


def test_reserve_and_unreserve(wishlist):
    wish = wishlist.wishes.get(wish="Kolo")
    data = put(Client(), wishlist, wish.id).json()
    assert data["reserved_count"] == 1 and data["secret"]

    data = put(Client(), wishlist, wish.id, data["secret"]).json()
    assert data == {"reserved_count": 0, "error": ""}


def test_reserved_wish_cannot_be_reserved_again_and_secret_does_not_leak(wishlist):
    wish = wishlist.wishes.get(wish="Kolo")
    secret = put(Client(), wishlist, wish.id).json()["secret"]

    response = put(Client(), wishlist, wish.id)
    assert response.status_code == 409
    assert secret not in response.content.decode()

    wish.refresh_from_db()
    assert wish.reserved_count == 1


def test_wrong_secret_cannot_unreserve(wishlist):
    wish = wishlist.wishes.get(wish="Kolo")
    put(Client(), wishlist, wish.id)
    response = put(Client(), wishlist, wish.id, "deadbeef")
    assert response.status_code == 403
    wish.refresh_from_db()
    assert wish.reserved_count == 1


def test_old_secret_is_invalid_after_reset(owner, wishlist):
    wish = wishlist.wishes.get(wish="Kolo")
    old_secret = put(Client(), wishlist, wish.id).json()["secret"]
    owner.post(wishlist.get_absolute_url(), {"reset_reservations": "doit"})
    put(Client(), wishlist, wish.id)  # someone else reserves

    response = put(Client(), wishlist, wish.id, old_secret)
    assert response.status_code == 403
    wish.refresh_from_db()
    assert wish.reserved_count == 1


def test_multiple_reservation(wishlist):
    wish = wishlist.wishes.get(wish="Ponožky")
    first = put(Client(), wishlist, wish.id).json()
    second = put(Client(), wishlist, wish.id).json()
    assert second["reserved_count"] == 2
    put(Client(), wishlist, wish.id, first["secret"])
    wish.refresh_from_db()
    assert wish.reserved_count == 1


@pytest.mark.parametrize(
    "body, status",
    [
        ("not json", 400),
        ("[]", 400),
        ('{"wish_id": "abc"}', 400),
        ("{}", 400),
        ('{"wish_id": 999999}', 404),
    ],
)
def test_reserve_invalid_requests(wishlist, body, status):
    response = Client().put(wishlist.get_absolute_url(), body, content_type="application/json")
    assert response.status_code == status
    assert response.json()["error"]


def test_reserve_wish_from_other_wishlist(wishlist):
    other = WishList.objects.create(name="Jiný")
    other_wish = Wish.objects.create(wishlist=other, wish="Cizí")
    assert put(Client(), wishlist, other_wish.id).status_code == 404


def test_reserve_in_missing_wishlist(db):
    response = Client().put("/neexistuje/", json.dumps({"wish_id": 1}), content_type="application/json")
    assert response.status_code == 404
