(() => {
  const shop = document.querySelector("#shop");
  if (!shop) return;
  let activeRequest;

  const showShopError = () => {
    let status = shop.querySelector(".shop-update-error");
    if (!status) {
      status = document.createElement("p");
      status.className = "shop-update-error";
      status.setAttribute("role", "status");
      shop.querySelector("#shop-content").prepend(status);
    }
    status.textContent = "We couldn’t update the seafood list. Please try again.";
  };

  const loadShopContent = async (url, updateHistory = true) => {
    activeRequest?.abort();
    const controller = new AbortController();
    activeRequest = controller;
    shop.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(url, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error(`Shop request failed: ${response.status}`);
      const html = await response.text();
      if (activeRequest !== controller) return;
      const parsed = new DOMParser().parseFromString(html, "text/html");
      const replacement = parsed.querySelector("#shop-content");
      const current = shop.querySelector("#shop-content");
      if (!replacement || !current) throw new Error("Shop response did not contain shop content.");
      current.replaceWith(replacement);
      if (updateHistory) history.pushState({}, "", url);
    } catch (error) {
      if (error.name === "AbortError") return;
      if (activeRequest !== controller) return;
      console.error("Could not update the shop section.", error);
      showShopError();
    } finally {
      if (activeRequest === controller) shop.setAttribute("aria-busy", "false");
    }
  };

  shop.addEventListener("click", (event) => {
    const link = event.target instanceof Element ? event.target.closest(".category-tile") : null;
    if (!link || event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
    event.preventDefault();
    loadShopContent(link.href);
  });

  shop.addEventListener("submit", (event) => {
    const form = event.target.closest(".search-form");
    if (!form) return;
    event.preventDefault();
    const url = new URL(form.action, window.location.href);
    const formData = new FormData(form);
    for (const [key, value] of formData) {
      if (value) url.searchParams.set(key, value.toString());
      else url.searchParams.delete(key);
    }
    loadShopContent(url);
  });

  window.addEventListener("popstate", () => loadShopContent(window.location.href, false));
})();
