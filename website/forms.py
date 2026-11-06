import re

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError

from .models import ContactInquiry, CustomerProfile

User = get_user_model()


def _username_for_email(email):
    usernames = list(
        User.objects.filter(email__iexact=email).values_list("username", flat=True)[:2]
    )
    if len(usernames) == 1:
        return usernames[0]
    return email.strip().lower()


class CustomerRegistrationForm(forms.Form):
    full_name = forms.CharField(max_length=150, label="Name")
    phone = forms.CharField(max_length=24, label="Phone number")
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput, label="Password")
    confirm_password = forms.CharField(widget=forms.PasswordInput, label="Confirm password")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists() or User.objects.filter(
            username__iexact=email
        ).exists():
            raise ValidationError("An account with this email already exists.")
        return email

    def clean_phone(self):
        phone = re.sub(r"\D", "", self.cleaned_data["phone"])
        if not 7 <= len(phone) <= 15:
            raise ValidationError("Enter a valid phone number, including country code if needed.")
        if CustomerProfile.objects.filter(phone=phone).exists():
            raise ValidationError("An account with this phone number already exists.")
        return phone

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        confirm_password = cleaned_data.get("confirm_password")
        if password and confirm_password and password != confirm_password:
            self.add_error("confirm_password", "The passwords do not match.")
        if password:
            user = User(
                username=cleaned_data.get("email", ""),
                email=cleaned_data.get("email", ""),
                first_name=cleaned_data.get("full_name", ""),
            )
            try:
                validate_password(password, user=user)
            except ValidationError as error:
                self.add_error("password", error)
        return cleaned_data

    def save(self):
        full_name = self.cleaned_data["full_name"].strip().split(maxsplit=1)
        user = User.objects.create_user(
            username=self.cleaned_data["email"],
            email=self.cleaned_data["email"],
            first_name=full_name[0],
            last_name=full_name[1] if len(full_name) > 1 else "",
            password=self.cleaned_data["password"],
        )
        CustomerProfile.objects.create(user=user, phone=self.cleaned_data["phone"])
        return user


class ContactInquiryForm(forms.ModelForm):
    class Meta:
        model = ContactInquiry
        fields = ("name", "email", "phone", "subject", "message")
        widgets = {
            "name": forms.TextInput(attrs={"autocomplete": "name", "placeholder": "Your name"}),
            "email": forms.EmailInput(attrs={"autocomplete": "email", "placeholder": "you@example.com"}),
            "phone": forms.TelInput(attrs={"autocomplete": "tel", "placeholder": "Optional"}),
            "subject": forms.TextInput(attrs={"placeholder": "How can we help?"}),
            "message": forms.Textarea(
                attrs={"rows": 5, "placeholder": "Write your message here…"}
            ),
        }


class CustomerAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email address or staff username",
        widget=forms.TextInput(attrs={"autocomplete": "username", "autofocus": True}),
    )

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if "@" in username:
            return _username_for_email(username)
        return username


class CheckoutForm(forms.Form):
    full_name = forms.CharField(max_length=120, label="Full name")
    phone = forms.CharField(max_length=24, label="Mobile number")
    email = forms.EmailField(required=False, label="Email address")
    address = forms.CharField(max_length=240, label="Street address")
    city = forms.CharField(max_length=100)
    postcode = forms.RegexField(regex=r"^\d{6}$", max_length=6, min_length=6, label="PIN code")
    notes = forms.CharField(max_length=400, required=False)

    def clean_phone(self):
        phone = re.sub(r"\D", "", self.cleaned_data["phone"])
        if not 7 <= len(phone) <= 15:
            raise ValidationError("Enter a valid mobile number, including country code if needed.")
        return phone

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
