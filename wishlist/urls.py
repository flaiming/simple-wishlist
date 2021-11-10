from django.conf.urls import url

from wishlist.views import WishlistIntro, WishlistView

urlpatterns = [
    url(r"^$", WishlistIntro.as_view(), name="wishlist-intro"),
    url(r"^nove$", WishlistView.as_view(), name="wishlist-create"),
    url(r"^(?P<slug>[\w\d]+)/$", WishlistView.as_view(), name="wishlist-detail"),
]
