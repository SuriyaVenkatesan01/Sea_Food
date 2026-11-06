document.querySelectorAll(".message-stack .notice, .portal-messages .notice").forEach((notice) => {
  window.setTimeout(() => {
    notice.classList.add("notice-dismissing");
    window.setTimeout(() => notice.remove(), 300);
  }, 4700);
});
