from django.db import migrations, models


def seed_positions(apps, schema_editor):
    Wish = apps.get_model("wishlist", "Wish")
    WishList = apps.get_model("wishlist", "WishList")
    for wishlist in WishList.objects.all().iterator():
        wishes = Wish.objects.filter(wishlist=wishlist).order_by("created", "id").values_list("id", flat=True)
        for position, wish_id in enumerate(wishes, start=1):
            Wish.objects.filter(pk=wish_id).update(position=position)


def reverse_seed_positions(apps, schema_editor):
    # nothing to do; keep existing ordering
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("wishlist", "0003_wishlist_description"),
    ]

    operations = [
        migrations.AddField(
            model_name="wish",
            name="position",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AlterModelOptions(
            name="wish",
            options={"ordering": ("position", "created", "id")},
        ),
        migrations.RunPython(seed_positions, reverse_code=reverse_seed_positions),
    ]
