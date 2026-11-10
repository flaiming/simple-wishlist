# Changelog

All notable changes to this project. The project has no version numbers, entries are grouped by release date.

## 2026-11-10

### Added
- Photos in wishlist description: up to 10 photos per wishlist (e.g. a photo of a letter to Santa), multiple files can be selected at once, single photos can be deleted.
- Photo gallery: clicking a photo opens it in a lightbox (GLightbox) with swipe/keyboard navigation instead of a new tab.
- Uploaded photos are rotated by EXIF, shrunk to max. 1600 px, re-encoded as JPEG with all metadata (incl. GPS location) stripped and stored under random names. Files are deleted together with the photo or wishlist.
- Photos are listed as inline in Django admin.
- `MEDIA_URL` / `MEDIA_ROOT` settings, Pillow dependency.

## 2026-11-01

### Security
- Only the owner (edit slug in session) can edit, delete, reset or forget an existing wishlist; strangers get 403 and no longer receive the edit slug.
- Reservation secret is returned only on successful reservation and rotated when a wish becomes reserved; reservations use conditional updates to avoid races.
- Wish text is escaped (stored XSS).
- Tokens are generated with the `secrets` module, edit slug is longer.

### Fixed
- 404 for missing wishlist/wish, 400 for invalid reservation request, custom 403/404 pages.
- Copy-to-clipboard buttons no longer submit the form.
- Stale local reservations are dropped after the owner resets them.
- Session lasts a year, so owners keep edit access.

### Changed
- Upgraded to Django 5.2 LTS and django-bootstrap4 25.3, updated dev tools and pre-commit hooks.
- Added view tests.

## 2025-11-09

### Added
- Wishlist description.
- Drag & drop ordering of wishes.

### Changed
- Better deleting of wishes.
- Django update, ruff rules in `pyproject.toml`.

## 2023-11-25

### Changed
- Updated Django, other packages and pre-commit hooks.

## 2021-11

### Added
- Intro page, "My wishlists" in menu and option to forget a wishlist on the device.
- Button to delete a wishlist.
- Owner can reset all reservations.
- pytest.

### Changed
- Bootstrap 3 → 4, production moved to sdilejprani.cz.
- Django 3.2, pre-commit with black, isort and flake8.

## 2019–2021

### Changed
- Migrated to Python 3, Django 2.2 and later security updates.
- Polite form of address in texts.

## 2018-11 – 2018-12

### Added
- Initial version: wishlists without registration, share and edit links, reservations.
- Option to send the edit link to e-mail.
- Multiple reservations of one wish with a count of reservations.
- Bold heading of a wish (text before ` - `).
- Select share/edit link on click, option to forget the edit slug.
