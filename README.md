# simple-wishlist

Wishlist as simple as it can be. No registration, just fill in wishes and share with others. They can mark wishes as reserved so others know that this wish is no longer available.

Demo site: https://sdilejprani.cz

![image](https://github.com/user-attachments/assets/ad9c4fb7-4e84-4870-9bec-b7cdc89d7195)

## Features

- **No accounts.** Every wishlist gets two secret links:
  - a *share link* (`/<slug>/`) for family and friends,
  - an *edit link* (`/<slug>/?edit_slug=...`) for the owner. Opening it stores edit access in the session (for a year), so the owner can come back without the link. The edit link can also be sent to the owner's e-mail.
- **Wishes** with optional bold heading (text before ` - ` on the first line is bold), clickable links, drag & drop ordering and an option to allow multiple reservations of one wish.
- **Description and photos.** A wishlist can have a text description and up to 10 photos (e.g. a photo of a letter to Santa). Photos are shown as a gallery with a lightbox (swipe/keyboard navigation).
- **Reservations** without accounts. Whoever reserves a wish gets a secret stored in their browser's `localStorage`, so only they can cancel the reservation. The owner doesn't see who reserved what, but can reset all reservations.
- **"My wishlists"** menu lists wishlists the current browser can edit; the owner can make the browser forget a wishlist.

### Uploaded photos

Every uploaded photo is processed with Pillow before it is stored:

- rotated according to EXIF orientation (photos from phones aren't sideways),
- shrunk to at most 1600 px on the longer side and re-encoded as JPEG (transparent PNGs get a white background),
- **all metadata is stripped**, including GPS location,
- stored under a random, unguessable name in `media/wishlists/`.

Limits: 20 MB per uploaded file, 10 photos per wishlist (`MAX_IMAGE_UPLOAD_SIZE` and `MAX_IMAGES` in `wishlist/forms.py`). Files are deleted from disk when a photo or the whole wishlist is deleted.

## Tech stack

- Python 3.10+, Django 5.2 LTS, SQLite
- django-bootstrap4 (Bootstrap 4), jQuery, Font Awesome
- Pillow (image processing)
- SortableJS (drag & drop ordering) and GLightbox (photo gallery), loaded from jsDelivr

## Development

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# create simplewishlist/local.py, see below
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```

`simplewishlist/local.py` (gitignored) holds local/production settings and is used by `manage.py`, `wsgi.py` and pytest:

```python
from simplewishlist.settings import *  # noqa

DEBUG = True
SECRET_KEY = "change-me"
ALLOWED_HOSTS = ["*"]
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
WEB_URL = "http://localhost:8000"
```

With `DEBUG = True` Django serves uploaded media itself.

### Tests and linters

```sh
.venv/bin/python -m pytest
pre-commit run --all-files  # isort, black, ruff, flake8
```

## Deployment

Production runs uWSGI behind nginx. Besides the usual `migrate` and `collectstatic`, nginx has to:

- serve uploaded files: `location /media/ { alias /path/to/project/media/; }` (with `DEBUG = False` Django doesn't serve them),
- allow photo uploads: `client_max_body_size 100m;` (one request can carry several phone photos; nginx default is 1 MB).

The uWSGI process needs write access to `media/`.

Changes are listed in [CHANGELOG.md](CHANGELOG.md).
