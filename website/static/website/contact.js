(() => {
  const form = document.querySelector(".contact-form[data-contact-invalid='true']");
  if (form) {
    document.querySelector("#contact")?.scrollIntoView({ behavior: "smooth" });
  }
})();
