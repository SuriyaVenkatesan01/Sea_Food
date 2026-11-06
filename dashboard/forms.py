from django import forms
from django.core.exceptions import ValidationError
from django.forms import inlineformset_factory
from django.utils.text import slugify

from website.models import Product, Store, StorePincode


class ProductForm(forms.ModelForm):
    slug = forms.SlugField(required=False)

    class Meta:
        model = Product
        fields = (
            "name",
            "slug",
            "category",
            "description",
            "image_url",
            "price",
            "compare_at_price",
            "weight",
            "stock",
            "is_featured",
            "is_active",
        )
        widgets = {
            "description": forms.Textarea(attrs={"rows": 4}),
            "is_featured": forms.CheckboxInput(),
            "is_active": forms.CheckboxInput(),
        }

    def clean_slug(self):
        slug = slugify(self.cleaned_data.get("slug") or self.cleaned_data["name"])
        if not slug:
            raise ValidationError("Enter a product name that can be used to create a URL.")
        products = Product.objects.filter(slug=slug)
        if self.instance.pk:
            products = products.exclude(pk=self.instance.pk)
        base_slug = slug
        suffix = 2
        while products.exists():
            slug = f"{base_slug}-{suffix}"
            products = Product.objects.filter(slug=slug)
            if self.instance.pk:
                products = products.exclude(pk=self.instance.pk)
            suffix += 1
        return slug


class StoreForm(forms.ModelForm):
    class Meta:
        model = Store
        fields = (
            "name",
            "address",
            "city",
            "phone",
            "latitude",
            "longitude",
            "delivery_radius_km",
            "is_active",
        )
        widgets = {
            "address": forms.TextInput(attrs={"autocomplete": "street-address"}),
            "latitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "e.g. 13.0827"}),
            "longitude": forms.NumberInput(attrs={"step": "0.000001", "placeholder": "e.g. 80.2707"}),
            "delivery_radius_km": forms.NumberInput(attrs={"step": "0.01", "min": "0.01"}),
            "is_active": forms.CheckboxInput(),
        }


class StorePincodeForm(forms.ModelForm):
    class Meta:
        model = StorePincode
        fields = ("postcode", "priority")
        widgets = {
            "postcode": forms.TextInput(
                attrs={"inputmode": "numeric", "pattern": "[0-9]{6}", "maxlength": "6"}
            ),
            "priority": forms.NumberInput(attrs={"min": "0"}),
        }


StorePincodeFormSet = inlineformset_factory(
    Store,
    StorePincode,
    form=StorePincodeForm,
    extra=1,
    can_delete=True,
)
