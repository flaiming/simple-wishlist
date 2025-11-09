from django.conf import settings
from django.db import models
from django.urls import reverse

from .utils import create_hash


class WishList(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField("Kdo jsi?", max_length=100)
    description = models.TextField("Popis seznamu (nepovinné)", blank=True, default="")
    slug = models.CharField(max_length=8, unique=True)
    edit_slug = models.CharField(max_length=8, unique=True)

    def __str__(self):
        return "Wishlist %s (%s)" % (self.slug, self.name)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = create_hash()
        if not self.edit_slug:
            self.edit_slug = create_hash(self.name, length=24)
        super(WishList, self).save(*args, **kwargs)

    @property
    def share_link(self) -> str:
        return settings.WEB_URL + reverse("wishlist-detail", args=[self.slug])

    @property
    def edit_link(self) -> str:
        return "%s%s?edit_slug=%s" % (
            settings.WEB_URL,
            reverse("wishlist-detail", args=[self.slug]),
            self.edit_slug,
        )

    @property
    def reserved_count(self) -> int:
        total = 0
        for wish in self.wishes.all():
            total += wish.reserved_count
        return total

    def get_absolute_url(self):
        return reverse("wishlist-detail", args=(self.slug,))


class Wish(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    wish = models.TextField("Zde napiš, co si přeješ.")
    multiple_reservation = models.BooleanField("Lze rezervovat vícekrát", default=False)
    reserved_count = models.PositiveIntegerField(default=0)
    secret = models.CharField(max_length=8)

    wishlist = models.ForeignKey(WishList, related_name="wishes", on_delete=models.CASCADE)

    def __str__(self):
        return self.wish

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = create_hash()
        super(Wish, self).save(*args, **kwargs)

    @property
    def wish_highlighted(self):
        if " - " in self.wish.splitlines()[0]:
            parts = self.wish.split(" - ")
            return "<strong>%s</strong> - %s" % (parts[0], " - ".join(parts[1:]))
        return self.wish
