document.querySelectorAll("[data-pincode-form]").forEach((form) => {
  const feedback = form.querySelector("[data-pincode-feedback]");
  const latitudeField = form.querySelector("[data-location-latitude]");
  const longitudeField = form.querySelector("[data-location-longitude]");
  const postcodeField = form.elements.postcode;
  const submitButton = form.querySelector('button[type="submit"]');

  postcodeField.addEventListener("input", () => {
    delete form.dataset.checkedPostcode;
    submitButton.textContent = "Check PIN availability →";
    feedback.textContent = "";
    feedback.classList.remove("pincode-error", "pincode-success");
  });

  form.addEventListener("submit", async (event) => {
    const postcode = form.elements.postcode.value.trim();
    if (!/^\d{6}$/.test(postcode)) {
      return;
    }

    event.preventDefault();
    if (form.dataset.checkedPostcode === postcode) {
      form.submit();
      return;
    }
    feedback.textContent = "Checking PIN code and store coverage…";
    feedback.classList.remove("pincode-error", "pincode-success");

    try {
      const url = new URL(form.dataset.lookupUrl, window.location.origin);
      url.searchParams.set("postcode", postcode);
      if (latitudeField.value && longitudeField.value) {
        url.searchParams.set("latitude", latitudeField.value);
        url.searchParams.set("longitude", longitudeField.value);
      }
      const response = await fetch(url, { headers: { Accept: "application/json" } });
      const result = await response.json();

      if (response.status === 503) {
        feedback.textContent = result.error;
        form.submit();
        return;
      }
      if (!response.ok) {
        throw new Error(result.error || "Could not check this PIN code.");
      }
      if (!result.serviceable) {
        feedback.textContent = result.message;
        feedback.classList.add("pincode-error");
        return;
      }

      feedback.textContent = result.message;
      if (result.serviceable) {
        form.dataset.checkedPostcode = postcode;
        feedback.classList.add("pincode-success");
        submitButton.textContent = "Use this delivery area →";
      } else {
        feedback.classList.add("pincode-error");
      }
    } catch (error) {
      feedback.textContent = `${error.message || "Online PIN lookup unavailable."} Checking our registered delivery areas instead.`;
      form.submit();
    }
  });

  form.querySelector("[data-location-button]")?.addEventListener("click", () => {
    delete form.dataset.checkedPostcode;
    submitButton.textContent = "Check PIN availability →";
    if (!navigator.geolocation) {
      feedback.textContent = "Location is unavailable in this browser. Enter your PIN code manually.";
      feedback.classList.add("pincode-error");
      return;
    }

    feedback.textContent = "Allow location access to find your PIN and nearest serving store.";
    feedback.classList.remove("pincode-error");
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        latitudeField.value = position.coords.latitude.toFixed(6);
        longitudeField.value = position.coords.longitude.toFixed(6);
        if (/^\d{6}$/.test(postcodeField.value.trim())) {
          form.requestSubmit();
          return;
        }

        try {
          const url = new URL(form.dataset.geocodeUrl, window.location.origin);
          url.searchParams.set("latitude", latitudeField.value);
          url.searchParams.set("longitude", longitudeField.value);
          const response = await fetch(url, { headers: { Accept: "application/json" } });
          const result = await response.json();
          if (!response.ok) {
            throw new Error(result.error || "Could not find a PIN for your location.");
          }
          postcodeField.value = result.postcode;
          feedback.textContent = `Found PIN ${result.postcode}. Checking nearby store coverage…`;
          form.requestSubmit();
        } catch (error) {
          feedback.textContent = `${error.message || "Location lookup unavailable."} Enter your PIN manually.`;
          feedback.classList.add("pincode-error");
          postcodeField.focus();
        }
      },
      (error) => {
        feedback.textContent = error.code === error.PERMISSION_DENIED
          ? "Location permission was denied. Enter your PIN manually."
          : "Could not read your location. Enter your PIN manually.";
        feedback.classList.add("pincode-error");
      },
      { enableHighAccuracy: false, timeout: 10000, maximumAge: 300000 },
    );
  });
});

document.querySelectorAll("[data-open-delivery-modal]").forEach((button) => {
  button.addEventListener("click", () => {
    const modal = document.querySelector("[data-delivery-modal]");
    modal.hidden = false;
    modal.querySelector('[name="postcode"]').focus();
  });
});
