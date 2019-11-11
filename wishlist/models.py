# -*- coding: utf-8 -*-

import hashlib
import datetime
import random
import sys

from django.urls import reverse
from django.conf import settings
from django.db import models
from django.contrib.sites.models import Site


class WishList(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    name = models.CharField("Kdo jste?", max_length=100)
    slug = models.CharField(max_length=8, unique=True)
    edit_slug = models.CharField(max_length=8, unique=True)

    def __unicode__(self):
        return "Wishlist %s (%s)" % (self.slug, self.name)

    def create_hash(self, text=''):
        h = hashlib.sha1()
        data = [
            datetime.datetime.now().isoformat(),
            self.name,
            str(random.randint(0, sys.maxsize)),
            settings.SECRET_KEY,
            text,
        ]
        h.update(("".join(data)).encode('utf-8'))
        return h.hexdigest()[:8]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self.create_hash()
        if not self.edit_slug:
            self.edit_slug = self.create_hash('edit')
        super(WishList, self).save(*args, **kwargs)

    @property
    def share_link(self):
        return "http://%s%s" % (Site.objects.get_current().domain, reverse('wishlist-detail', args=[self.slug]))

    @property
    def edit_link(self):
        return "http://%s%s?edit_slug=%s" % (Site.objects.get_current().domain, reverse('wishlist-detail', args=[self.slug]), self.edit_slug)

    def get_absolute_url(self):
        return reverse('wishlist-detail', args=(self.slug, ))


class Wish(models.Model):
    created = models.DateTimeField(auto_now_add=True)
    wish = models.TextField("Zde napište, co si přejete.")
    multiple_reservation = models.BooleanField("Lze rezervovat vícekrát", default=False)
    reserved_count = models.PositiveIntegerField(default=0)
    secret = models.CharField(max_length=8)

    wishlist = models.ForeignKey(WishList, related_name='wishes')

    def __unicode__(self):
        return self.wish

    def create_hash(self):
        h = hashlib.sha1()
        data = [
            datetime.datetime.now().isoformat(),
            self.wish,
            str(random.randint(0, sys.maxsize)),
            settings.SECRET_KEY,
        ]
        h.update(("".join(data)).encode('utf-8'))
        return h.hexdigest()[:8]

    def save(self, *args, **kwargs):
        if not self.secret:
            self.secret = self.create_hash()
        super(Wish, self).save(*args, **kwargs)

    @property
    def wish_highlighted(self):
        if ' - ' in self.wish.splitlines()[0]:
            parts = self.wish.split(' - ')
            return "<strong>%s</strong> - %s" % (parts[0], ' - '.join(parts[1:]))
        return self.wish
