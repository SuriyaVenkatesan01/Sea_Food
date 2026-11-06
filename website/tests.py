from decimal import Decimal
from io import BytesIO
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import ContactInquiry, CustomerProfile, Order, OrderItem, Product, Store, StorePincode


class StorefrontTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="asha@example.com",
            email="asha@example.com",
            password="secure-password-987",
            first_name="Asha",
            last_name="Customer",
        )
        CustomerProfile.objects.create(user=self.user, phone="919876543210")
        self.client.force_login(self.user)
        self.store = Store.objects.create(name="Chennai Central", city="Chennai")
        StorePincode.objects.create(store=self.store, postcode="600001")
        session = self.client.session
        session["delivery_postcode"] = "600001"
        session["delivery_store_id"] = self.store.id
        session.save()
        self.product = Product.objects.create(
            name="Coastal Prawns",
            slug="coastal-prawns",
            category=Product.Category.PRAWNS,
            price=Decimal("400.00"),
            stock=5,
        )

    def test_products_page_displays_active_products_and_filters_by_category(self):
        hidden = Product.objects.create(
            name="Hidden Fish",
            slug="hidden-fish",
            category=Product.Category.FISH,
            price=Decimal("250.00"),
            stock=4,
            is_active=False,
        )

        response = self.client.get(reverse("website:products"))
        self.assertContains(response, self.product.name)
        self.assertNotContains(response, hidden.name)

        response = self.client.get(reverse("website:products"), {"category": Product.Category.FISH})
        self.assertNotContains(response, self.product.name)

    def test_homepage_displays_full_searchable_product_catalog(self):
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, self.product.name)
        self.assertContains(response, "Our fresh catch")
        self.assertContains(response, 'class="category-tiles"')
        self.assertContains(response, 'id="product-search"')
        self.assertContains(response, 'action="{}"'.format(reverse("website:home")))

        hidden = Product.objects.create(
            name="Hidden Fish",
            slug="hidden-fish",
            category=Product.Category.FISH,
            price=Decimal("250.00"),
            stock=4,
            is_active=False,
        )
        response = self.client.get(reverse("website:home"))
        self.assertNotContains(response, hidden.name)

    def test_homepage_filters_products_by_search_and_category(self):
        fish = Product.objects.create(
            name="Fresh Sea Bass",
            slug="fresh-sea-bass",
            category=Product.Category.FISH,
            price=Decimal("520.00"),
            stock=4,
        )
        response = self.client.get(
            reverse("website:home"),
            {"category": Product.Category.FISH, "q": "Sea"},
        )
        self.assertContains(response, fish.name)
        self.assertNotContains(response, self.product.name)

    def test_products_page_renders_centered_image_based_category_tiles(self):
        self.product.image_url = "https://example.com/prawns.jpg"
        self.product.save(update_fields=["image_url"])
        response = self.client.get(reverse("website:products"))
        self.assertContains(response, 'class="category-tiles"')
        self.assertContains(response, 'class="category-tile-image"')
        self.assertContains(response, "All seafood")
        self.assertContains(response, "Prawns")
        self.assertContains(response, "https://example.com/prawns.jpg")

    def test_header_shows_one_sign_in_link_without_registration_or_staff_links(self):
        self.client.logout()
        response = self.client.get(reverse("website:home"))
        self.assertContains(
            response,
            'class="text-link sign-in-link" href="{}">Sign in'.format(reverse("website:login")),
        )
        nav_actions = response.content.decode().split('<div class="nav-actions">', 1)[1].split("</div>", 1)[0]
        self.assertNotIn(">Create account</a>", nav_actions)
        self.assertNotIn(">Staff</a>", nav_actions)
        self.assertContains(response, 'class="cart-icon"')
        self.assertNotContains(response, '<span class="cart-icon">♧</span>')
        self.assertContains(response, 'href="{}">Products</a>'.format(reverse("website:products")))
        self.assertContains(response, 'href="{}">About</a>'.format(reverse("website:about")))
        self.assertContains(response, 'href="{}">Contact</a>'.format(reverse("website:contact")))

    def test_shop_category_filter_returns_only_shop_fragment_for_ajax(self):
        fish = Product.objects.create(
            name="Fresh Sea Bass",
            slug="fresh-sea-bass",
            category=Product.Category.FISH,
            price=Decimal("520.00"),
            stock=4,
        )
        response = self.client.get(
            reverse("website:products"),
            {"category": Product.Category.FISH},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, 'id="shop-content"')
        self.assertContains(response, fish.name)
        self.assertNotContains(response, self.product.name)
        self.assertNotContains(response, "THE DAY’S FRESHEST CATCH")
        self.assertNotContains(response, "<header")

    def test_shop_search_ajax_keeps_selected_category(self):
        response = self.client.get(
            reverse("website:products"),
            {"category": Product.Category.PRAWNS, "q": "Coastal"},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        self.assertContains(response, self.product.name)
        self.assertContains(response, 'name="category" value="prawns"')
        self.assertNotContains(response, "Fresh Sea Bass")

    def test_homepage_links_to_separate_storefront_pages(self):
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, reverse("website:products"))
        self.assertContains(response, reverse("website:about"))
        self.assertContains(response, reverse("website:contact"))
        self.assertNotContains(response, 'class="contact-form"')

    def test_contact_page_shows_store_contact_details_and_contact_form(self):
        response = self.client.get(reverse("website:contact"))
        self.assertContains(response, 'id="contact"')
        self.assertContains(response, "hello@tideandtable.example")
        self.assertContains(response, "Chennai, Tamil Nadu, India")
        self.assertContains(response, reverse("website:contact_submit"))
        self.assertNotContains(response, "Our fresh catch")

    def test_about_page_shows_store_story_and_products_link(self):
        response = self.client.get(reverse("website:about"))
        self.assertContains(response, "About Tide & Table")
        self.assertContains(response, "Good seafood should feel simple.")
        self.assertContains(response, reverse("website:products"))

    def test_contact_form_submission_is_saved_and_returns_to_contact_page(self):
        response = self.client.post(
            reverse("website:contact_submit"),
            {
                "name": "Mira Customer",
                "email": "mira@example.com",
                "phone": "9876543210",
                "subject": "Fresh fish availability",
                "message": "Do you have sea bass today?",
            },
        )
        inquiry = ContactInquiry.objects.get()
        self.assertRedirects(response, reverse("website:contact"))
        self.assertEqual(inquiry.name, "Mira Customer")
        self.assertEqual(inquiry.email, "mira@example.com")
        self.assertFalse(inquiry.is_resolved)

    def test_invalid_contact_form_is_rendered_again_without_saving(self):
        response = self.client.post(
            reverse("website:contact_submit"),
            {
                "name": "",
                "email": "not-an-email",
                "phone": "",
                "subject": "",
                "message": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-contact-invalid="true"')
        self.assertContains(response, 'id="contact"')
        self.assertContains(response, "This field is required.")
        self.assertEqual(ContactInquiry.objects.count(), 0)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_cart_add_checkout_emails_invoice_and_tracking_link(self):
        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        response = self.client.post(
            reverse("website:checkout"),
            {
                "full_name": "Asha Customer",
                "phone": "919876543210",
                "email": "asha@example.com",
                "address": "12 Sea Road",
                "city": "Chennai",
                "postcode": "600001",
                "notes": "",
            },
        )

        order = Order.objects.get()
        self.assertRegex(order.reference, r"^[A-Z0-9]{6}$")
        self.assertRedirects(response, reverse("website:order_success", args=[order.reference]))
        self.assertEqual(order.customer, self.user)
        self.assertEqual(order.store.name, "Chennai Central")
        self.assertEqual(order.phone, "919876543210")
        self.assertEqual(order.total, Decimal("449.00"))
        self.assertEqual(order.items.get().quantity, 1)
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.client.session["cart"], {})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ["asha@example.com"])
        self.assertEqual(mail.outbox[0].from_email, "Avee Foods <aveeoils@gmail.com>")
        self.assertIn("Avee Foods", mail.outbox[0].subject)
        self.assertIn("Avee Foods INVOICE", mail.outbox[0].body)
        self.assertIn(order.reference, mail.outbox[0].body)
        self.assertIn(f"?reference={order.reference}", mail.outbox[0].body)
        self.assertIn("Track your order", mail.outbox[0].alternatives[0][0])

    def test_tracking_link_prefills_alphanumeric_order_reference(self):
        response = self.client.get(
            reverse("website:track_guest_order"),
            {"reference": "DUFOU8"},
        )

        self.assertContains(response, 'name="lookup" required value="DUFOU8"')

    def test_order_reference_retries_when_alphanumeric_id_is_already_used(self):
        Order.objects.create(
            reference="ABC123",
            full_name="Existing Customer",
            phone="919876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("100.00"),
            total=Decimal("100.00"),
        )
        with patch("website.models.secrets.choice", side_effect=list("ABC123DUFOU8")):
            order = Order.objects.create(
                full_name="New Customer",
                phone="919876543211",
                address="15 Sea Road",
                city="Chennai",
                postcode="600001",
                subtotal=Decimal("100.00"),
                total=Decimal("100.00"),
            )

        self.assertEqual(order.reference, "DUFOU8")

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_guest_can_place_order_and_track_with_reference_and_matching_phone(self):
        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        self.client.logout()
        session = self.client.session
        session["cart"] = {str(self.product.id): 1}
        session["delivery_postcode"] = "600001"
        session.save()
        response = self.client.post(
            reverse("website:checkout"),
            {
                "full_name": "Guest Customer",
                "phone": "+91 98765 43210",
                "email": "guest@example.com",
                "address": "12 Sea Road",
                "city": "Chennai",
                "postcode": "600001",
                "notes": "",
            },
        )
        order = Order.objects.get()
        self.assertRedirects(response, reverse("website:order_success", args=[order.reference]))
        self.assertIsNone(order.customer)
        self.assertEqual(order.phone, "919876543210")
        self.assertEqual(order.store.name, "Chennai Central")
        self.assertEqual(self.client.get(reverse("website:order_success", args=[order.reference])).status_code, 200)

        response = self.client.post(
            reverse("website:track_guest_order"),
            {"reference": order.reference.lower(), "phone": "+91 98765 43210"},
        )
        self.assertContains(response, "ORDER REFERENCE")
        self.assertContains(response, order.reference)

        response = self.client.post(
            reverse("website:track_guest_order"),
            {"reference": order.reference, "phone": "919999999999"},
        )
        self.assertNotContains(response, "Serving store: Chennai Central")

    def test_guest_can_track_order_with_reference_without_signing_in(self):
        self.client.logout()
        order = Order.objects.create(
            reference="4XTVFW",
            full_name="Guest Customer",
            phone="919876543210",
            email="guest@example.com",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("100.00"),
            total=Decimal("149.00"),
        )

        response = self.client.post(
            reverse("website:track_guest_order"),
            {"lookup": order.reference},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#4XTVFW")
        self.assertContains(response, "Created")
        self.assertContains(response, 'aria-current="step"')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_guest_can_track_recent_orders_with_checkout_mobile_without_signing_in(self):
        self.client.logout()
        first_order = Order.objects.create(
            reference="DUFOU8",
            full_name="Guest Customer",
            phone="919876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("100.00"),
            total=Decimal("149.00"),
            status=Order.Status.PREPARING,
        )
        Order.objects.create(
            reference="HQZZ6X",
            full_name="Guest Customer",
            phone="919876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("200.00"),
            total=Decimal("249.00"),
            status=Order.Status.OUT_FOR_DELIVERY,
        )

        response = self.client.post(
            reverse("website:track_guest_order"),
            {"lookup": "+91 98765 43210"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "#DUFOU8")
        self.assertContains(response, "#HQZZ6X")
        self.assertContains(response, "Packing")
        self.assertContains(response, "Dispatched")
        self.assertContains(response, 'aria-current="step"')
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_guest_tracking_shows_delivered_as_final_timeline_step(self):
        self.client.logout()
        Order.objects.create(
            reference="ABC123",
            full_name="Guest Customer",
            phone="919876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("100.00"),
            total=Decimal("149.00"),
            status=Order.Status.DELIVERED,
        )

        response = self.client.post(
            reverse("website:track_guest_order"),
            {"lookup": "ABC123"},
        )

        self.assertContains(response, "Delivered")
        self.assertContains(response, 'class="tracking-step tracking-step-current" aria-current="step"')

    def test_delivery_area_can_be_changed_and_unsupported_pin_is_rejected(self):
        response = self.client.post(
            reverse("website:select_delivery_area"),
            {"postcode": "600002", "next": reverse("website:home")},
        )
        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600001")

        store = Store.objects.create(name="South Chennai")
        StorePincode.objects.create(store=store, postcode="600002")
        response = self.client.post(
            reverse("website:select_delivery_area"),
            {"postcode": "600002", "next": reverse("website:home")},
        )
        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600002")

    def test_pincode_only_selection_uses_highest_priority_store(self):
        priority_store = Store.objects.create(name="Priority Store")
        StorePincode.objects.create(
            store=priority_store,
            postcode="600001",
            priority=5,
        )

        response = self.client.post(
            reverse("website:select_delivery_area"),
            {"postcode": "600001", "next": reverse("website:home")},
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_store_id"], priority_store.id)

    def test_first_visit_prompts_for_pin_before_showing_storefront(self):
        session = self.client.session
        session.pop("delivery_postcode")
        session.save()

        response = self.client.get(reverse("website:home"))

        self.assertContains(response, 'class="delivery-modal-backdrop"')
        self.assertContains(response, "Where should we deliver?")
        self.assertContains(response, "Use my location to find the nearest store")
        self.assertContains(response, "Location is optional.")
        self.assertContains(response, "Close delivery PIN prompt")
        self.assertContains(response, "Check PIN availability")

    def test_delivery_modal_can_be_opened_when_a_delivery_pin_is_already_saved(self):
        response = self.client.get(reverse("website:home"))

        self.assertContains(response, 'data-open-delivery-modal')
        self.assertContains(response, 'data-delivery-modal')
        self.assertContains(response, 'id="first-delivery-postcode" name="postcode" value="600001"')
        self.assertContains(response, "Close delivery PIN prompt")

    def test_delivery_prompt_can_be_closed_without_location_or_pin(self):
        session = self.client.session
        session.pop("delivery_postcode")
        session.pop("delivery_store_id")
        session.save()
        response = self.client.post(
            reverse("website:dismiss_delivery_prompt"),
            {"next": reverse("website:home")},
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertTrue(self.client.session["delivery_prompt_dismissed"])
        self.assertNotIn("delivery_postcode", self.client.session)
        response = self.client.get(reverse("website:home"))
        self.assertContains(response, 'class="delivery-modal-backdrop" hidden')
        self.assertContains(response, "Choose your delivery area")

    def test_closing_pin_prompt_does_not_allow_checkout_without_coverage(self):
        session = self.client.session
        session.pop("delivery_postcode")
        session.pop("delivery_store_id")
        session.save()
        self.client.post(reverse("website:dismiss_delivery_prompt"))
        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))

        response = self.client.get(reverse("website:checkout"))

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(Order.objects.count(), 0)

    @patch("website.views.urlopen")
    def test_online_pin_lookup_returns_location_and_assigned_store(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = BytesIO(
            b'[{"Status":"Success","PostOffice":[{"District":"Chennai","State":"Tamil Nadu"}]}]'
        )

        response = self.client.get(reverse("website:lookup_delivery_postcode"), {"postcode": "600001"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {
                "valid": True,
                "serviceable": True,
                "location": "Chennai, Tamil Nadu",
                "store": "Chennai Central",
                "distance_km": None,
                "message": "Delivery available in Chennai, Tamil Nadu through Chennai Central.",
            },
        )
        mock_urlopen.assert_called_once_with(
            "https://api.postalpincode.in/pincode/600001", timeout=4
        )

    @override_settings(GOOGLE_MAPS_API_KEY="test-google-key")
    @patch("website.views.urlopen")
    def test_google_location_lookup_returns_six_digit_postcode(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = BytesIO(
            b'{"status":"OK","results":[{"address_components":'
            b'[{"long_name":"600001","types":["postal_code"]}]}]}'
        )

        response = self.client.get(
            reverse("website:lookup_location_postcode"),
            {"latitude": "13.0827", "longitude": "80.2707"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"postcode": "600001"})
        self.assertIn(
            "https://maps.googleapis.com/maps/api/geocode/json?",
            mock_urlopen.call_args.args[0],
        )
        self.assertIn("key=test-google-key", mock_urlopen.call_args.args[0])

    @override_settings(GOOGLE_MAPS_API_KEY="")
    @patch("website.views.urlopen")
    def test_google_location_lookup_without_key_requests_manual_postcode(self, mock_urlopen):
        response = self.client.get(
            reverse("website:lookup_location_postcode"),
            {"latitude": "13.0827", "longitude": "80.2707"},
        )

        self.assertEqual(response.status_code, 503)
        self.assertIn("manually", response.json()["error"])
        mock_urlopen.assert_not_called()

    @override_settings(GOOGLE_MAPS_API_KEY="test-google-key")
    @patch("website.views.urlopen")
    def test_google_location_lookup_rejects_response_without_postcode(self, mock_urlopen):
        mock_urlopen.return_value.__enter__.return_value = BytesIO(
            b'{"status":"OK","results":[{"address_components":'
            b'[{"long_name":"Chennai","types":["locality"]}]}]}'
        )

        response = self.client.get(
            reverse("website:lookup_location_postcode"),
            {"latitude": "13.0827", "longitude": "80.2707"},
        )

        self.assertEqual(response.status_code, 404)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_location_selection_uses_nearest_store_within_configured_radius(self):
        nearer_store = Store.objects.create(
            name="Marina Store",
            latitude=Decimal("13.080000"),
            longitude=Decimal("80.300000"),
            delivery_radius_km=Decimal("10.00"),
        )
        StorePincode.objects.create(store=nearer_store, postcode="600001")
        farther_store = Store.objects.create(
            name="Central Store",
            latitude=Decimal("13.000000"),
            longitude=Decimal("80.200000"),
            delivery_radius_km=Decimal("10.00"),
        )
        StorePincode.objects.create(store=farther_store, postcode="600001")
        response = self.client.post(
            reverse("website:select_delivery_area"),
            {
                "postcode": "600001",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "next": reverse("website:home"),
            },
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600001")
        self.assertEqual(self.client.session["delivery_store_id"], nearer_store.id)
        self.assertNotIn("delivery_latitude", self.client.session)
        self.assertNotIn("delivery_longitude", self.client.session)

        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        self.client.post(
            reverse("website:checkout"),
            {
                "full_name": "Asha Customer",
                "phone": "919876543210",
                "email": "asha@example.com",
                "address": "12 Sea Road",
                "city": "Chennai",
                "postcode": "600001",
                "notes": "",
            },
        )
        order = Order.objects.get()
        self.assertEqual(order.store, nearer_store)

    def test_location_match_routes_to_nearby_store_even_without_matching_pincode(self):
        nearby_store = Store.objects.create(
            name="Nearby Store",
            latitude=Decimal("13.080000"),
            longitude=Decimal("80.300000"),
            delivery_radius_km=Decimal("10.00"),
        )
        StorePincode.objects.create(store=nearby_store, postcode="600002")

        response = self.client.post(
            reverse("website:select_delivery_area"),
            {
                "postcode": "600001",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "next": reverse("website:home"),
            },
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600001")
        self.assertEqual(self.client.session["delivery_store_id"], nearby_store.id)

    def test_pincode_match_routes_when_customer_location_is_outside_store_radii(self):
        Store.objects.create(
            name="Distant Geocoded Store",
            latitude=Decimal("13.000000"),
            longitude=Decimal("80.000000"),
            delivery_radius_km=Decimal("1.00"),
        )

        response = self.client.post(
            reverse("website:select_delivery_area"),
            {
                "postcode": "600001",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "next": reverse("website:home"),
            },
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600001")
        self.assertEqual(self.client.session["delivery_store_id"], self.store.id)

    def test_location_outside_all_store_radii_is_rejected(self):
        Store.objects.create(
            name="Far Store",
            latitude=Decimal("13.000000"),
            longitude=Decimal("80.000000"),
            delivery_radius_km=Decimal("1.00"),
        )
        response = self.client.post(
            reverse("website:select_delivery_area"),
            {
                "postcode": "600001",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "next": reverse("website:home"),
            },
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(self.client.session["delivery_postcode"], "600001")
        self.assertEqual(self.client.session["delivery_store_id"], self.store.id)

    def test_location_uses_nearest_store_that_is_inside_its_radius(self):
        nearest_but_out_of_range = Store.objects.create(
            name="Close Store",
            latitude=Decimal("13.082000"),
            longitude=Decimal("80.270000"),
            delivery_radius_km=Decimal("0.01"),
        )
        StorePincode.objects.create(store=nearest_but_out_of_range, postcode="600001")
        farther_but_in_range = Store.objects.create(
            name="Available Store",
            latitude=Decimal("13.090000"),
            longitude=Decimal("80.280000"),
            delivery_radius_km=Decimal("5.00"),
        )
        StorePincode.objects.create(store=farther_but_in_range, postcode="600001")

        response = self.client.post(
            reverse("website:select_delivery_area"),
            {
                "postcode": "600001",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "next": reverse("website:home"),
            },
        )

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(
            self.client.session["delivery_store_id"],
            farther_but_in_range.id,
        )

    def test_checkout_requires_a_supported_delivery_pin(self):
        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        session = self.client.session
        session.pop("delivery_postcode")
        session.save()
        response = self.client.get(reverse("website:checkout"))
        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_rejects_empty_basket(self):
        response = self.client.get(reverse("website:checkout"))
        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(Order.objects.count(), 0)

    def test_order_cannot_exceed_available_stock_at_checkout(self):
        self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        self.product.stock = 0
        self.product.save(update_fields=["stock"])

        response = self.client.post(reverse("website:checkout"))

        self.assertRedirects(response, reverse("website:home"))
        self.assertEqual(Order.objects.count(), 0)

    def test_cart_add_caps_quantity_at_inventory(self):
        for _ in range(7):
            self.client.post(reverse("website:add_to_cart", args=[self.product.id]))
        self.assertEqual(self.client.session["cart"][str(self.product.id)], 5)


class DashboardTests(TestCase):
    def setUp(self):
        self.store = Store.objects.create(name="Chennai Central", city="Chennai")
        self.product = Product.objects.create(
            name="Fresh Fish",
            slug="fresh-fish",
            category=Product.Category.FISH,
            price=Decimal("300.00"),
            stock=3,
        )
        self.order = Order.objects.create(
            store=self.store,
            full_name="Asha Customer",
            phone="9876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("300.00"),
            total=Decimal("349.00"),
            delivery_fee=Decimal("49.00"),
        )
        OrderItem.objects.create(
            order=self.order,
            product=self.product,
            product_name=self.product.name,
            unit_price=self.product.price,
            quantity=1,
        )

    def test_dashboard_requires_staff_access(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertRedirects(
            response,
            f"{reverse('dashboard:login')}?next={reverse('dashboard:overview')}",
            fetch_redirect_response=False,
        )

    def test_staff_can_view_dashboard_and_cancel_order_restocking_items(self):
        staff = get_user_model().objects.create_user(
            username="store-manager", password="test-password", is_staff=True
        )
        self.client.force_login(staff)
        response = self.client.get(reverse("dashboard:overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.order.reference)
        self.assertContains(response, "Chennai Central")

        response = self.client.post(
            reverse("dashboard:update_order_status", args=[self.order.id]),
            {"status": Order.Status.CANCELLED},
        )

        self.assertRedirects(response, reverse("dashboard:overview"))
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)

        self.client.post(
            reverse("dashboard:update_order_status", args=[self.order.id]),
            {"status": Order.Status.DELIVERED},
        )
        self.product.refresh_from_db()
        self.order.refresh_from_db()
        self.assertEqual(self.product.stock, 4)
        self.assertEqual(self.order.status, Order.Status.CANCELLED)


class DashboardManagementTests(TestCase):
    def setUp(self):
        staff = get_user_model().objects.create_user(
            username="store-manager", password="secure-password-987", is_staff=True
        )
        self.client.force_login(staff)
        self.product = Product.objects.create(
            name="Fresh Fish",
            slug="fresh-fish",
            category=Product.Category.FISH,
            price=Decimal("300.00"),
            stock=3,
        )
        self.order = Order.objects.create(
            full_name="Asha Customer",
            phone="9876543210",
            email="asha@example.com",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("300.00"),
            total=Decimal("349.00"),
        )

    def test_staff_can_add_store_with_multiple_service_pincodes(self):
        response = self.client.post(
            reverse("dashboard:store_create"),
            {
                "name": "Marina Seafood",
                "address": "1 Beach Road",
                "city": "Chennai",
                "phone": "04412345678",
                "latitude": "13.082700",
                "longitude": "80.270700",
                "delivery_radius_km": "12.00",
                "is_active": "on",
                "service_areas-TOTAL_FORMS": "2",
                "service_areas-INITIAL_FORMS": "0",
                "service_areas-MIN_NUM_FORMS": "0",
                "service_areas-MAX_NUM_FORMS": "1000",
                "service_areas-0-postcode": "600001",
                "service_areas-0-priority": "1",
                "service_areas-1-postcode": "600002",
                "service_areas-1-priority": "2",
            },
        )

        self.assertRedirects(response, reverse("dashboard:stores"))
        store = Store.objects.get(name="Marina Seafood")
        self.assertEqual(
            list(store.service_areas.order_by("postcode").values_list("postcode", "priority")),
            [("600001", 1), ("600002", 2)],
        )

    def test_staff_can_assign_same_pincode_to_multiple_stores(self):
        store = Store.objects.create(name="South Store")
        StorePincode.objects.create(store=store, postcode="600001")

        response = self.client.post(
            reverse("dashboard:store_create"),
            {
                "name": "North Store",
                "city": "Chennai",
                "delivery_radius_km": "15.00",
                "is_active": "on",
                "service_areas-TOTAL_FORMS": "1",
                "service_areas-INITIAL_FORMS": "0",
                "service_areas-MIN_NUM_FORMS": "0",
                "service_areas-MAX_NUM_FORMS": "1000",
                "service_areas-0-postcode": "600001",
                "service_areas-0-priority": "3",
            },
        )

        self.assertRedirects(response, reverse("dashboard:stores"))
        self.assertEqual(StorePincode.objects.filter(postcode="600001").count(), 2)

    def test_staff_can_add_store_from_dashboard_ui(self):
        response = self.client.get(reverse("dashboard:stores"))
        self.assertContains(response, "Stores & PIN codes")
        self.assertContains(response, reverse("dashboard:store_create"))
        response = self.client.get(reverse("dashboard:store_create"))
        self.assertContains(response, "Delivery radius")
        self.assertContains(response, "Service PIN codes")
        self.assertContains(response, 'data-add-pincode')
        self.assertContains(response, "latitude")
        self.assertContains(response, "longitude")

    def test_staff_can_edit_store_service_pincodes(self):
        store = Store.objects.create(name="Editable Store")
        StorePincode.objects.create(store=store, postcode="600001", priority=1)
        response = self.client.post(
            reverse("dashboard:store_edit", args=[store.id]),
            {
                "name": "Updated Store",
                "city": "Chennai",
                "delivery_radius_km": "15.00",
                "is_active": "on",
                "service_areas-TOTAL_FORMS": "1",
                "service_areas-INITIAL_FORMS": "1",
                "service_areas-MIN_NUM_FORMS": "0",
                "service_areas-MAX_NUM_FORMS": "1000",
                "service_areas-0-id": str(store.service_areas.get().id),
                "service_areas-0-store": str(store.id),
                "service_areas-0-postcode": "600003",
                "service_areas-0-priority": "4",
            },
        )

        self.assertRedirects(response, reverse("dashboard:stores"))
        store.refresh_from_db()
        self.assertEqual(store.name, "Updated Store")
        self.assertEqual(store.service_areas.get().postcode, "600003")
        self.assertEqual(store.service_areas.get().priority, 4)

    def test_store_management_requires_staff_access(self):
        self.client.logout()

        response = self.client.get(reverse("dashboard:stores"))

        self.assertRedirects(
            response,
            f"{reverse('dashboard:login')}?next={reverse('dashboard:stores')}",
            fetch_redirect_response=False,
        )

    def test_staff_can_add_product_and_slug_is_generated(self):
        response = self.client.post(
            reverse("dashboard:product_create"),
            {
                "name": "Coastal Prawns",
                "slug": "",
                "category": Product.Category.PRAWNS,
                "description": "Fresh catch",
                "image_url": "",
                "price": "420.00",
                "compare_at_price": "",
                "weight": "500 g",
                "stock": "12",
                "is_featured": "on",
                "is_active": "on",
            },
        )
        product = Product.objects.get(name="Coastal Prawns")
        self.assertRedirects(response, reverse("dashboard:products"))
        self.assertEqual(product.slug, "coastal-prawns")
        self.assertEqual(product.stock, 12)
        self.assertTrue(product.is_featured)
        self.assertTrue(product.is_active)

    def test_product_management_pages_render(self):
        response = self.client.get(reverse("dashboard:products"))
        self.assertContains(response, self.product.name)
        response = self.client.get(reverse("dashboard:product_create"))
        self.assertContains(response, "Add a product")

    def test_staff_can_edit_inventory_and_deactivate_product(self):
        response = self.client.post(
            reverse("dashboard:product_edit", args=[self.product.id]),
            {
                "name": self.product.name,
                "slug": self.product.slug,
                "category": self.product.category,
                "description": "",
                "image_url": "",
                "price": "350.00",
                "compare_at_price": "",
                "weight": "500 g",
                "stock": "18",
            },
        )
        self.product.refresh_from_db()
        self.assertRedirects(response, reverse("dashboard:products"))
        self.assertEqual(self.product.price, Decimal("350.00"))
        self.assertEqual(self.product.stock, 18)
        self.assertFalse(self.product.is_active)

    def test_order_tracker_searches_and_filters_orders(self):
        delivered_order = Order.objects.create(
            full_name="Mira Customer",
            phone="919876543210",
            address="99 Sea Road",
            city="Chennai",
            postcode="600002",
            subtotal=Decimal("200.00"),
            total=Decimal("249.00"),
            status=Order.Status.DELIVERED,
        )
        response = self.client.get(
            reverse("dashboard:orders"),
            {"q": "asha@example.com", "status": Order.Status.NEW},
        )
        self.assertContains(response, self.order.reference)
        self.assertNotContains(response, delivered_order.reference)

    def test_contacts_page_shows_and_searches_storefront_contact_submissions(self):
        response = self.client.post(
            reverse("website:contact_submit"),
            {
                "name": "Mira Customer",
                "email": "mira@example.com",
                "phone": "9876543210",
                "subject": "Fresh fish availability",
                "message": "Do you have sea bass today?",
            },
        )
        self.assertRedirects(response, reverse("website:contact"))

        response = self.client.get(reverse("dashboard:contacts"), {"q": "mira@example.com"})
        self.assertContains(response, "CUSTOMER SUPPORT")
        self.assertContains(response, 'class="orders-table contact-submissions-table"')
        self.assertContains(response, "<th scope=\"col\">CUSTOMER</th>")
        self.assertContains(response, "<th scope=\"col\">MESSAGE</th>")
        self.assertContains(response, "<th scope=\"col\">STATUS</th>")
        self.assertContains(response, "Fresh fish availability")
        self.assertContains(response, "Do you have sea bass today?")
        self.assertContains(response, "Add product")
        self.assertContains(response, reverse("dashboard:orders"))

        response = self.client.get(reverse("dashboard:contacts"), {"q": "no-such-customer"})
        self.assertNotContains(response, "Fresh fish availability")
        self.assertContains(response, "No contact submissions yet")

    def test_order_status_update_returns_to_filtered_tracker(self):
        tracker_url = f"{reverse('dashboard:orders')}?status={Order.Status.NEW}"
        response = self.client.post(
            reverse("dashboard:update_order_status", args=[self.order.id]),
            {"status": Order.Status.CONFIRMED, "next": tracker_url},
        )
        self.order.refresh_from_db()
        self.assertRedirects(response, tracker_url)
        self.assertEqual(self.order.status, Order.Status.CONFIRMED)

    def test_staff_can_view_contact_messages_and_mark_them_resolved(self):
        inquiry = ContactInquiry.objects.create(
            name="Mira Customer",
            email="mira@example.com",
            subject="Delivery question",
            message="Can I update my delivery address?",
        )
        response = self.client.get(reverse("dashboard:inquiries"), {"q": "mira@example.com"})
        self.assertContains(response, inquiry.subject)
        self.assertContains(response, "Mark resolved")

        response = self.client.post(reverse("dashboard:resolve_inquiry", args=[inquiry.id]))
        inquiry.refresh_from_db()
        self.assertRedirects(response, reverse("dashboard:inquiries"))
        self.assertTrue(inquiry.is_resolved)


class CustomerAccountTests(TestCase):
    def test_login_page_has_light_seafood_image_layout(self):
        response = self.client.get(reverse("website:login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="auth-login-page"')
        self.assertContains(response, 'class="login-background-image"')
        self.assertContains(response, "premium_photo-1717345994192-f5bc10b61c09")
        self.assertContains(response, 'class="login-background-overlay"')
        self.assertContains(response, 'class="auth-card"')

    def test_registration_requires_matching_passwords_and_creates_customer_profile(self):
        payload = {
            "full_name": "Mira Customer",
            "phone": "+91 98765 43210",
            "email": "Mira@example.com",
            "password": "strong-password-1234",
            "confirm_password": "different-password-1234",
        }
        response = self.client.post(reverse("website:register"), payload)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(get_user_model().objects.filter(email="mira@example.com").exists())

        payload["confirm_password"] = payload["password"]
        response = self.client.post(reverse("website:register"), payload)
        self.assertRedirects(response, reverse("website:login"))
        user = get_user_model().objects.get(email="mira@example.com")
        self.assertEqual(user.customer_profile.phone, "919876543210")

    def test_customer_can_login_and_track_only_their_own_phone_orders(self):
        user = get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="secure-password-987",
        )
        CustomerProfile.objects.create(user=user, phone="919876543210")
        own_order = Order.objects.create(
            customer=user,
            full_name="Mira Customer",
            phone="919876543210",
            address="12 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("100.00"),
            total=Decimal("149.00"),
        )
        other_user = get_user_model().objects.create_user(
            username="other@example.com",
            email="other@example.com",
            password="secure-password-987",
        )
        CustomerProfile.objects.create(user=other_user, phone="919999999999")
        Order.objects.create(
            customer=other_user,
            full_name="Other Customer",
            phone="919876543210",
            address="99 Sea Road",
            city="Chennai",
            postcode="600001",
            subtotal=Decimal("200.00"),
            total=Decimal("249.00"),
        )

        response = self.client.post(
            reverse("website:login"),
            {"username": "CUSTOMER@example.com", "password": "secure-password-987"},
        )
        self.assertRedirects(response, reverse("website:track_orders"))
        response = self.client.post(reverse("website:track_orders"), {"phone": "+91 98765 43210"})
        self.assertContains(response, own_order.reference)
        self.assertNotContains(response, "Other Customer")
        response = self.client.post(reverse("website:track_orders"), {"phone": "919999999999"})
        self.assertNotContains(response, own_order.reference)

    def test_unified_login_accepts_customers_and_staff_by_role(self):
        customer = get_user_model().objects.create_user(
            username="customer@example.com",
            email="customer@example.com",
            password="secure-password-987",
        )
        CustomerProfile.objects.create(user=customer, phone="919876543210")
        response = self.client.post(
            reverse("website:login"),
            {"username": "customer@example.com", "password": "secure-password-987"},
        )
        self.assertRedirects(response, reverse("website:track_orders"))
        self.client.logout()

        staff = get_user_model().objects.create_user(
            username="store-manager",
            email="store@example.com",
            password="secure-password-987",
            is_staff=True,
        )
        response = self.client.post(
            reverse("website:login"),
            {"username": staff.username, "password": "secure-password-987"},
        )
        self.assertRedirects(response, reverse("dashboard:overview"))

    def test_staff_can_sign_in_from_customer_page_using_email(self):
        staff = get_user_model().objects.create_user(
            username="store-manager",
            email="store@example.com",
            password="secure-password-987",
            is_staff=True,
        )
        response = self.client.post(
            reverse("website:login"),
            {"username": staff.email.upper(), "password": "secure-password-987"},
        )
        self.assertRedirects(response, reverse("dashboard:overview"))

    def test_dashboard_login_redirects_to_unified_login_and_preserves_next(self):
        response = self.client.get(reverse("dashboard:overview"))
        self.assertRedirects(
            response,
            f"{reverse('dashboard:login')}?next={reverse('dashboard:overview')}",
            fetch_redirect_response=False,
        )
        response = self.client.get(response["Location"])
        self.assertRedirects(
            response,
            f"{reverse('website:login')}?next={reverse('dashboard:overview')}",
            fetch_redirect_response=False,
        )
        response = self.client.get(response["Location"])
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Sign in to place orders or manage the store.")
