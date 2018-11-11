from django.conf.urls import include, url
from django.contrib import admin
from wishlist.views import WishlistView


urlpatterns = [
    url(r'^admin/', admin.site.urls),

    url(r'^$', WishlistView.as_view(), name='wishlist-home'),
    url(r'^(?P<slug>[\w\d]+)/$', WishlistView.as_view(), name='wishlist-detail'),
]
