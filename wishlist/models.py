from django.conf import settings
from django.db import models
from django.db.models import Max, Sum
from django.urls import reverse
from django.utils.html import escape, format_html

from .utils import create_hash

SLUG_LENGTH = 8
EDIT_SLUG_LENGTH = 24


def unique_hash(model, field: str, length: int) -> str:
    while True:
        value = create_hash(length)
        if not model.objects.filter(**{field: value}).exists():
            return value


class WishList(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField("Kdo jsi?", max_length=100)
    description = models.TextField("Popis seznamu (nepovinné)", blank=True, default="")
    slug = models.CharField(max_length=SLUG_LENGTH, unique=True)
    edit_slug = models.CharField(max_length=32, unique=True)

    def __str__(self):
        return f"Wishlist {self.slug} ({self.name})"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = unique_hash(WishList, "slug", SLUG_LENGTH)
        if not self.edit_slug:
            self.edit_slug = unique_hash(WishList, "edit_slug", EDIT_SLUG_LENGTH)
        super().save(*args, **kwargs)

    @property
    def share_link(self) -> str:
        return settings.WEB_URL + reverse("wishlist-detail", args=[self.slug])

    @property
    def edit_link(self) -> str:
        return f"{self.share_link}?edit_slug={self.edit_slug}"

    @property
    def reserved_count(self) -> int:
        return self.wishes.aggregate(total=Sum("reserved_count"))["total"] or 0

    def get_absolute_url(self):
        return reverse("wishlist-detail", args=(self.slug,))


class Wish(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    wish = models.TextField("Zde napiš, co si přeješ.")
    multiple_reservation = models.BooleanField("Lze rezervovat vícekrát", default=False)
    reserved_count = models.PositiveIntegerField(default=0)
    secret = models.CharField(max_length=8)
    position = models.PositiveIntegerField(default=0)

    wishlist = models.ForeignKey(WishList, related_name="wishes", on_delete=models.CASCADE)

    class Meta:
        ordering = ("position", "created", "id")

    def __str__(self):
        return self.wish

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = create_hash()
        if not self.position:
            last_position = self.wishlist.wishes.aggregate(Max("position")).get("position__max") if self.wishlist_id else None
            self.position = (last_position or 0) + 1
        super().save(*args, **kwargs)

    @property
    def wish_highlighted(self):
        """
        Escaped wish text with the part before the first " - " (on the first line) in bold.
        """
        first_line = self.wish.splitlines()[0] if self.wish else ""
        if " - " in first_line:
            head, tail = self.wish.split(" - ", 1)
            return format_html("<strong>{}</strong> - {}", head, tail)
        return escape(self.wish)
