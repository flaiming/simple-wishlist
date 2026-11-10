from io import BytesIO

from django import forms
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.mail import send_mail
from PIL import Image, ImageOps

from wishlist.models import Wish, WishList, WishListImage

MAX_IMAGES = 10
MAX_IMAGE_UPLOAD_SIZE = 20 * 1024 * 1024
MAX_IMAGE_SIDE = 1600


def process_image(uploaded) -> ContentFile:
    """
    Rotate image according to EXIF, shrink it and re-encode it as JPEG.
    Re-encoding also strips all metadata (e.g. GPS location of the photo).
    """
    uploaded.seek(0)
    with Image.open(uploaded) as original:
        img = ImageOps.exif_transpose(original)
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        if img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGBA")
            background = Image.new("RGB", img.size, "white")
            background.paste(img, mask=img.getchannel("A"))
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")
        buffer = BytesIO()
        img.save(buffer, "JPEG", quality=85, optimize=True)
    return ContentFile(buffer.getvalue(), name="image.jpg")


class WishForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["wish"].required = False

    class Meta:
        model = Wish
        fields = ["wish", "multiple_reservation", "position"]
        widgets = {
            "wish": forms.Textarea(attrs={"rows": 2}),
            "position": forms.HiddenInput(attrs={"class": "wish-position-field"}),
        }


class MultipleFileInput(forms.FileInput):
    allow_multiple_selected = True


class MultipleFileField(forms.FileField):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("widget", MultipleFileInput(attrs={"accept": "image/*", "class": "form-control-file"}))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            return [single_clean(d, initial) for d in data if d]
        return [single_clean(data, initial)] if data else []


class WishListForm(forms.ModelForm):
    images = MultipleFileField(label="Obrázky k popisu (nepovinné)", required=False)
    delete_images = forms.ModelMultipleChoiceField(queryset=WishListImage.objects.none(), required=False)
    email = forms.EmailField(label="Email pro zaslání odkazu pro úpravu (nepovinné)", required=False)

    class Meta:
        model = WishList
        fields = ["name", "description", "images", "delete_images", "email"]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3, "placeholder": "Popis seznamu přání (nepovinné)"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # only images of this wishlist can be deleted
            self.fields["delete_images"].queryset = self.instance.images.all()

    def clean_images(self):
        processed = []
        for image in self.cleaned_data.get("images") or []:
            if image.size > MAX_IMAGE_UPLOAD_SIZE:
                raise forms.ValidationError(
                    f"{image.name}: obrázek je příliš velký, maximum je {MAX_IMAGE_UPLOAD_SIZE // 1024 // 1024} MB."
                )
            try:
                processed.append(process_image(image))
            except (OSError, ValueError, Image.DecompressionBombError) as e:
                raise forms.ValidationError(f"{image.name}: obrázek se nepodařilo zpracovat, zkuste prosím jiný soubor.") from e
        return processed

    def clean(self):
        cleaned_data = super().clean()
        if "images" in cleaned_data:
            existing = self.instance.images.count() if self.instance.pk else 0
            total = existing - len(cleaned_data.get("delete_images") or []) + len(cleaned_data["images"])
            if total > MAX_IMAGES:
                self.add_error("images", f"Seznam může mít nejvýše {MAX_IMAGES} obrázků.")
        return cleaned_data

    def save(self, commit=True):
        email = self.cleaned_data["email"]
        super().save(commit=commit)
        for image in self.cleaned_data.get("delete_images") or []:
            image.delete()  # file is deleted from disk by post_delete signal
        for content in self.cleaned_data.get("images") or []:
            WishListImage.objects.create(wishlist=self.instance, image=content)
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
