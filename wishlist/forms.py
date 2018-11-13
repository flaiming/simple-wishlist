# -*- coding: utf-8 -*-
from django import forms
from wishlist.models import Wish, WishList
from django.forms.formsets import DELETION_FIELD_NAME
from django.utils.html import strip_tags


class WishForm(forms.ModelForm):

    class Meta:
        model = Wish
        fields = ['wish', 'multiple_reservation']
        widgets = {
            'wish': forms.Textarea(attrs={'rows': 2}),
        }
        labels = {
            DELETION_FIELD_NAME: 'ads',
        }

    def clean_wish(self):
        return strip_tags(self.cleaned_data['wish'])


class WishListForm(forms.ModelForm):

    class Meta:
        model = WishList
        fields = ['name']
