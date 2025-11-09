# -*- coding: utf-8 -*-
from django import forms
from django.conf import settings
from django.core.mail import send_mail
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.html import strip_tags

from wishlist.models import Wish, WishList


class WishForm(forms.ModelForm):
    class Meta:
        model = Wish
        fields = ["wish", "multiple_reservation"]
        widgets = {
            "wish": forms.Textarea(attrs={"rows": 2}),
        }
        labels = {
            DELETION_FIELD_NAME: "ads",
        }

    def clean_wish(self):
        return strip_tags(self.cleaned_data["wish"])


class WishListForm(forms.ModelForm):
    email = forms.EmailField(label="Email pro zaslání odkazu pro úpravu (nepovinné)", required=False)

    class Meta:
        model = WishList
        fields = ["name", "description", "email"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Popis seznamu přání (nepovinné)"}),
        }

    def save(self, commit=True):
        email = self.cleaned_data["email"]
        super(WishListForm, self).save(commit=commit)
        if email:
            # send user an email with edit link
            send_mail(
                "Odkaz pro úpravu seznamu přání",
                f"""Dobrý den,
posílám odkaz na úpravu Vašeho seznamu přání: {self.instance.edit_link}

Vojtěch Oram
{settings.WEB_URL}""",
                "vojtech@oram.cz",
                [email],
                fail_silently=True,
            )
