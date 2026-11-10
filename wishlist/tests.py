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


# ---------- wishlist image ----------


def make_image(fmt="JPEG", size=(3000, 2000), mode="RGB", exif_orientation=None) -> bytes:
    from io import BytesIO

    from PIL import Image

    img = Image.new(mode, size, "red")
    buffer = BytesIO()
    kwargs = {}
    if exif_orientation:
        exif = Image.Exif()
        exif[0x0112] = exif_orientation  # Orientation
        exif[0x8825] = {2: (50.0, 5.0, 0.0)}  # GPSInfo
        kwargs["exif"] = exif
    img.save(buffer, fmt, **kwargs)
    return buffer.getvalue()


def upload(content: bytes, name="foto.jpg"):
    from django.core.files.uploadedfile import SimpleUploadedFile

    return SimpleUploadedFile(name, content, content_type="image/jpeg")


@pytest.fixture
def media_root(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    return tmp_path


def stored_images(wishlist):
    from PIL import Image

    return [Image.open(i.image.path) for i in wishlist.images.all()]


def post_images(client, wishlist, files=(), delete=()):
    data = formset_data(wishlist)
    data["images"] = list(files)
    data["delete_images"] = [str(i.id) for i in delete]
    return client.post(wishlist.get_absolute_url(), data)


def test_owner_can_upload_multiple_images(owner, wishlist, media_root):
    response = post_images(owner, wishlist, [upload(make_image(exif_orientation=6)), upload(make_image(size=(50, 40)))])
    assert response.status_code == 302
    first, second = stored_images(wishlist)
    assert first.format == "JPEG"
    # rotated according to EXIF (3000x2000 -> portrait) and shrunk
    assert first.size == (1067, 1600)
    # metadata (incl. GPS location) are stripped
    assert not first.getexif()
    assert second.size == (50, 40)
    for image in wishlist.images.all():
        assert re.fullmatch(r"wishlists/[0-9a-f]{32}\.jpg", image.image.name)

    content = Client().get(wishlist.get_absolute_url()).content.decode()
    for image in wishlist.images.all():
        assert image.image.url in content


def test_create_wishlist_with_transparent_png(stranger, media_root):
    data = formset_data(None, wishes=[(None, "Kolo")])
    data["images"] = upload(make_image("PNG", size=(100, 50), mode="RGBA"), name="obrazek.png")
    response = stranger.post(reverse("wishlist-create"), data)
    assert response.status_code == 302
    [img] = stored_images(WishList.objects.get())
    assert (img.format, img.mode, img.size) == ("JPEG", "RGB", (100, 50))


def test_invalid_image_is_rejected(owner, wishlist, media_root):
    response = post_images(owner, wishlist, [upload(make_image(size=(50, 50))), upload(b"not an image", name="dopis.jpg")])
    assert response.status_code == 200
    assert "dopis.jpg" in response.context["wishlistform"].errors["images"][0]
    assert not wishlist.images.exists()


def test_too_big_image_is_rejected(owner, wishlist, media_root, monkeypatch):
    monkeypatch.setattr("wishlist.forms.MAX_IMAGE_UPLOAD_SIZE", 100)
    response = post_images(owner, wishlist, [upload(make_image(size=(50, 50)))])
    assert response.status_code == 200
    assert "příliš velký" in response.context["wishlistform"].errors["images"][0]


def test_max_images(owner, wishlist, media_root, monkeypatch):
    monkeypatch.setattr("wishlist.forms.MAX_IMAGES", 2)
    post_images(owner, wishlist, [upload(make_image(size=(10, 10))), upload(make_image(size=(10, 10)))])
    assert wishlist.images.count() == 2

    response = post_images(owner, wishlist, [upload(make_image(size=(10, 10)))])
    assert response.status_code == 200
    assert response.context["wishlistform"].errors["images"]
    assert wishlist.images.count() == 2

    # replacing one image within the same request is fine
    response = post_images(owner, wishlist, [upload(make_image(size=(10, 10)))], delete=wishlist.images.all()[:1])
    assert response.status_code == 302
    assert wishlist.images.count() == 2


def test_stranger_cannot_upload_image(stranger, wishlist, media_root):
    assert post_images(stranger, wishlist, [upload(make_image(size=(50, 50)))]).status_code == 403
    assert not wishlist.images.exists()


def test_saving_without_upload_keeps_images(owner, wishlist, media_root, django_capture_on_commit_callbacks):
    post_images(owner, wishlist, [upload(make_image(size=(50, 50)))])
    [image] = wishlist.images.all()

    with django_capture_on_commit_callbacks(execute=True):
        owner.post(wishlist.get_absolute_url(), formset_data(wishlist, name="Jan"))
    wishlist.refresh_from_db()
    assert wishlist.name == "Jan"
    assert list(wishlist.images.all()) == [image]
    assert (media_root / image.image.name).exists()


def test_delete_single_image(owner, wishlist, media_root, django_capture_on_commit_callbacks):
    post_images(owner, wishlist, [upload(make_image(size=(50, 50))), upload(make_image(size=(60, 60)))])
    first, second = wishlist.images.all()

    with django_capture_on_commit_callbacks(execute=True):
        assert post_images(owner, wishlist, delete=[first]).status_code == 302
    assert list(wishlist.images.all()) == [second]
    assert not (media_root / first.image.name).exists()
    assert (media_root / second.image.name).exists()


def test_cannot_delete_image_of_other_wishlist(owner, wishlist, media_root):
    other = WishList.objects.create(name="Jiný")
    other_image = other.images.create(image=upload(make_image(size=(10, 10))))
    response = post_images(owner, wishlist, delete=[other_image])
    assert response.status_code == 200
    assert response.context["wishlistform"].errors["delete_images"]
    assert other.images.exists()


def test_delete_wishlist_deletes_images(owner, wishlist, media_root, django_capture_on_commit_callbacks):
    post_images(owner, wishlist, [upload(make_image(size=(50, 50))), upload(make_image(size=(60, 60)))])
    paths = [media_root / i.image.name for i in wishlist.images.all()]
    assert all(p.exists() for p in paths)

    with django_capture_on_commit_callbacks(execute=True):
        owner.post(wishlist.get_absolute_url(), {"delete": "doit"})
    assert not any(p.exists() for p in paths)
