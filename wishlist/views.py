# -*- coding: utf-8 -*-
from __future__ import unicode_literals
import json

from django.urls import reverse
from django.http import HttpResponseRedirect, JsonResponse
from django.views.generic import TemplateView, DetailView
from django.forms import inlineformset_factory
from django.contrib import messages
from django.db.transaction import atomic

from wishlist.forms import WishForm, WishListForm
from wishlist.models import Wish, WishList
from django.forms.models import BaseInlineFormSet
from django.forms.formsets import DELETION_FIELD_NAME


class CustomInlineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super(CustomInlineFormSet, self).add_fields(form, index)
        form.fields[DELETION_FIELD_NAME].label = u"Smazat"


WishFormSet = inlineformset_factory(
    WishList,
    Wish,
    WishForm,
    extra=1,
    min_num=1,
    validate_min=True,
    formset=CustomInlineFormSet
)


class WishlistView(TemplateView):
    template_name = 'wishlist/wishlist.html'
    object = None

    def get_object(self):
        slug = self.kwargs.get('slug', None)
        if slug:
            self.object = WishList.objects.filter(slug=slug).first()
            return self.object
        return None

    def is_editing(self):
        edit_slug = self.get_edit_slug_from_session(self.kwargs.get('slug', ''))
        return self.object and edit_slug and self.object.edit_slug == edit_slug

    def get_context_data(self, **kwargs):
        context = super(WishlistView, self).get_context_data(**kwargs)
        wishlist = self.get_object()
        if wishlist:
            if self.is_editing():
                # EDIT
                pass
            else:
                # SHOW
                context['wishlist'] = wishlist
        context['wishformset'] = WishFormSet(instance=wishlist)
        context['wishlistform'] = WishListForm(instance=wishlist)
        context['is_editing'] = self.is_editing()
        context['is_creating'] = not wishlist
        context['wishlist'] = wishlist
        return context

    def get_edit_slug_from_session(self, slug):
        return (self.request.session.get('edit_slugs', {}) or {}).get(slug, None)

    def add_edit_slug_to_session(self, slug, edit_slug):
        edit_slugs = self.request.session.get('edit_slugs', {}) or {}
        edit_slugs[slug] = edit_slug
        self.request.session['edit_slugs'] = edit_slugs

    def get(self, request, slug=None, *args, **kwargs):
        wishlist = self.get_object()
        edit_slug = request.GET.get('edit_slug', None)
        if wishlist and edit_slug and wishlist.edit_slug == edit_slug:
            self.add_edit_slug_to_session(slug, edit_slug)
            return HttpResponseRedirect(reverse('wishlist-detail', args=[slug]))
        return super(WishlistView, self).get(request, *args, **kwargs)

    def post(self, request, slug=None, *args, **kwargs):
        wishlist = self.get_object()
        wishformset = WishFormSet(request.POST, instance=wishlist)
        wishlistform = WishListForm(request.POST, instance=wishlist)
        if wishformset.is_valid() and wishlistform.is_valid():
            with atomic():
                wishlistform.save()
                for wish in wishformset.save(commit=False):
                    wish.wishlist = wishlistform.instance
                    wish.save()
                for to_delete in wishformset.deleted_objects:
                    to_delete.delete()

            messages.add_message(request, messages.SUCCESS, u'Úspěšně uloženo.')
            if self.is_editing():
                return HttpResponseRedirect(reverse('wishlist-detail', args=[wishlistform.instance.slug]))
            else:
                return HttpResponseRedirect(reverse('wishlist-detail', args=[wishlistform.instance.slug]) + "?edit_slug=%s" % wishlistform.instance.edit_slug)

        context = self.get_context_data(**kwargs)
        context['wishformset'] = wishformset
        context['wishlistform'] = wishlistform
        return self.render_to_response(context)

    def put(self, request, *args, **kwargs):
        data = json.loads(request.body)
        secret = data.get('secret', '')
        wishlist = self.get_object()
        error = ""
        wish = wishlist.wishes.filter(pk=data.get('wish_id', 0)).first()
        if wish:
            if not wish.reserved_count or wish.multiple_reservation:
                wish.reserved_count += 1
                wish.save()
            elif wish.reserved_count and secret:
                # un-reserve wish
                wish.reserved_count -= 1
                wish.save()
            else:
                error = u"Toto přání je již rezervováno někým jiným."
        else:
            error = u"Wish does not exist."
        return JsonResponse({'secret': wish.secret if wish else '', 'error': error})
