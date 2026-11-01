import json

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import F
from django.db.transaction import atomic
from django.forms import inlineformset_factory
from django.forms.formsets import DELETION_FIELD_NAME
from django.forms.models import BaseInlineFormSet
from django.http import Http404, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from django.views.generic import TemplateView

from wishlist.forms import WishForm, WishListForm
from wishlist.models import Wish, WishList
from wishlist.utils import create_hash


class CustomInlineFormSet(BaseInlineFormSet):
    def add_fields(self, form, index):
        super().add_fields(form, index)
        form.fields[DELETION_FIELD_NAME].label = "Smazat"

    def clean(self):
        super().clean()
        for form in self.forms:
            if not hasattr(form, "cleaned_data"):
                continue
            if form.cleaned_data.get(DELETION_FIELD_NAME):
                continue
            wish_value = (form.cleaned_data.get("wish") or "").strip()
            if not wish_value:
                form.cleaned_data[DELETION_FIELD_NAME] = True


WishFormSet = inlineformset_factory(WishList, Wish, WishForm, extra=1, min_num=1, validate_min=True, formset=CustomInlineFormSet)


class WishListViewMixin:
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        slugs = self.get_all_slugs_from_session()
        context["active_wishlists"] = WishList.objects.filter(slug__in=slugs)
        return context

    def get_all_slugs_from_session(self):
        return set(self.request.session.get("edit_slugs", {}).keys())

    def get_edit_slug_from_session(self, slug):
        return (self.request.session.get("edit_slugs", {}) or {}).get(slug, None)

    def add_edit_slug_to_session(self, slug, edit_slug):
        edit_slugs = self.request.session.get("edit_slugs", {}) or {}
        edit_slugs[slug] = edit_slug
        self.request.session["edit_slugs"] = edit_slugs

    def remove_edit_slug_from_session(self, slug):
        edit_slugs = self.request.session.get("edit_slugs", {}) or {}
        if slug in edit_slugs:
            del edit_slugs[slug]
        self.request.session["edit_slugs"] = edit_slugs


class WishlistView(WishListViewMixin, TemplateView):
    template_name = "wishlist/wishlist.html"
    object = None

    def get_object(self):
        slug = self.kwargs.get("slug", None)
        if slug:
            self.object = WishList.objects.filter(slug=slug).first()
            return self.object
        return None

    def is_editing(self):
        edit_slug = self.get_edit_slug_from_session(self.kwargs.get("slug", ""))
        return self.object and edit_slug and self.object.edit_slug == edit_slug

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        wishlist = self.get_object()
        if wishlist:
            if self.is_editing():
                # EDIT
                pass
            else:
                # SHOW
                context["wishlist"] = wishlist
        context["wishformset"] = WishFormSet(instance=wishlist)
        context["wishlistform"] = WishListForm(instance=wishlist)
        context["is_editing"] = self.is_editing()
        context["is_creating"] = not wishlist
        context["wishlist"] = wishlist
        return context

    def get(self, request, slug=None, *args, **kwargs):
        """
        show wishlist
        """
        wishlist = self.get_object()
        if slug and not wishlist:
            raise Http404("Seznam přání neexistuje.")
        edit_slug = request.GET.get("edit_slug", None)
        if wishlist and edit_slug and wishlist.edit_slug == edit_slug:
            self.add_edit_slug_to_session(slug, edit_slug)
            return HttpResponseRedirect(reverse("wishlist-detail", args=[slug]))
        if request.GET.get("forget_edit_slug", ""):
            self.remove_edit_slug_from_session(slug)
        return super().get(request, *args, **kwargs)

    def post(self, request, slug=None, *args, **kwargs):
        """
        create/update wishlist
        """
        wishlist = self.get_object()
        if slug and not wishlist:
            raise Http404("Seznam přání neexistuje.")
        if wishlist and not self.is_editing():
            # only the owner (with edit slug stored in session) can modify existing wishlist
            raise PermissionDenied
        if wishlist:
            if request.POST.get("delete") == "doit":
                # delete this wishlist
                self.remove_edit_slug_from_session(wishlist.slug)
                wishlist.delete()
                messages.success(request, "Váš seznam přání byl úspěšně smazán.")
                return HttpResponseRedirect(reverse("wishlist-intro"))

            if request.POST.get("reset_reservations") == "doit":
                # reset all reservations
                wishlist.wishes.update(reserved_count=0)
                messages.success(request, "Rezervace byly resetovány.")
                return HttpResponseRedirect(wishlist.get_absolute_url())

            if request.POST.get("forget") == "doit":
                # remove this wishlist from session
                self.remove_edit_slug_from_session(wishlist.slug)
                messages.success(request, "Seznam přání byl zapomenut.")
                return HttpResponseRedirect(reverse("wishlist-intro"))

        original_wish_ids = set(wishlist.wishes.values_list("id", flat=True)) if wishlist else set()

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

                submitted_ids = set()
                deleted_ids = {obj.id for obj in wishformset.deleted_objects if obj.id}
                for form in wishformset.forms:
                    if not hasattr(form, "cleaned_data"):
                        continue
                    wish_obj = form.cleaned_data.get("id")
                    is_deleted = form.cleaned_data.get(DELETION_FIELD_NAME, False)
                    wish_value = (form.cleaned_data.get("wish") or "").strip()
                    if wish_obj and not is_deleted and wish_value:
                        submitted_ids.add(wish_obj.id)

                missing_ids = original_wish_ids - (submitted_ids | deleted_ids)
                if missing_ids:
                    wishlistform.instance.wishes.filter(id__in=missing_ids).delete()

            messages.add_message(request, messages.SUCCESS, "Úspěšně uloženo.")
            if self.is_editing():
                return HttpResponseRedirect(reverse("wishlist-detail", args=[wishlistform.instance.slug]))
            else:
                instance = wishlistform.instance
                return HttpResponseRedirect(f"{reverse('wishlist-detail', args=[instance.slug])}?edit_slug={instance.edit_slug}")

        context = self.get_context_data(**kwargs)
        context["wishformset"] = wishformset
        context["wishlistform"] = wishlistform
        return self.render_to_response(context)

    def put(self, request, *args, **kwargs):
        """
        (un)reserve wish

        Secret is returned only to the one who has just reserved the wish. It changes every time
        the wish goes from "not reserved" to "reserved", so old secrets cannot cancel new reservations.
        """
        wishlist = self.get_object()
        if not wishlist:
            return JsonResponse({"error": "Seznam přání neexistuje."}, status=404)
        try:
            data = json.loads(request.body.decode("utf-8"))
            wish_id = int(data.get("wish_id"))
            secret = str(data.get("secret") or "")
        except (ValueError, TypeError, AttributeError):
            return JsonResponse({"error": "Neplatný požadavek."}, status=400)

        wishes = Wish.objects.filter(wishlist=wishlist, pk=wish_id)
        if not wishes.exists():
            return JsonResponse({"error": "Toto přání neexistuje."}, status=404)

        if secret:
            # un-reserve wish
            if not wishes.filter(secret=secret).exists():
                return JsonResponse({"error": "Nemáte právo zrušit tuto rezervaci."}, status=403)
            wishes.filter(secret=secret, reserved_count__gt=0).update(reserved_count=F("reserved_count") - 1)
            return JsonResponse({"reserved_count": wishes.get().reserved_count, "error": ""})

        # reserve wish - conditional updates make it safe against concurrent requests
        new_secret = create_hash()
        reserved = wishes.filter(reserved_count=0).update(reserved_count=1, secret=new_secret) or wishes.filter(
            multiple_reservation=True
        ).update(reserved_count=F("reserved_count") + 1)
        if not reserved:
            return JsonResponse({"error": "Toto přání je již rezervováno někým jiným."}, status=409)
        wish = wishes.get()
        return JsonResponse({"secret": wish.secret, "reserved_count": wish.reserved_count, "error": ""})


class WishlistIntro(WishListViewMixin, TemplateView):
    template_name = "wishlist/intro.html"
