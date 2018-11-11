# -*- coding: utf-8 -*-
from django import forms
from wishlist.models import Wish, WishList
from django.forms.formsets import DELETION_FIELD_NAME


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


class WishListForm(forms.ModelForm):

    class Meta:
        model = WishList
        fields = ['name']
