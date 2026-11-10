from django.contrib import admin

from wishlist.models import WishList, WishListImage


class WishListImageInline(admin.TabularInline):
    model = WishListImage
    extra = 0


@admin.register(WishList)
class WishListAdmin(admin.ModelAdmin):
    inlines = [WishListImageInline]
