from django.conf.urls import url

from wishlist.views import WishlistView

urlpatterns = [
    url(r"^$", WishlistView.as_view(), name="wishlist-home"),
    url(r"^(?P<slug>[\w\d]+)/$", WishlistView.as_view(), name="wishlist-detail"),
]
