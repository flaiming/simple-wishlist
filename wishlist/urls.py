from django.urls import re_path

from wishlist.views import WishlistIntro, WishlistView

urlpatterns = [
    re_path(r"^$", WishlistIntro.as_view(), name="wishlist-intro"),
    re_path(r"^nove$", WishlistView.as_view(), name="wishlist-create"),
    re_path(r"^(?P<slug>[\w\d]+)/$", WishlistView.as_view(), name="wishlist-detail"),
]
