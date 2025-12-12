document.addEventListener("DOMContentLoaded", () => {
    const items = document.querySelectorAll(".sidebar-item");
    const current = window.location.pathname;

    items.forEach(item => {
        const href = item.dataset.href;

        if (current.startsWith(href)) {
            item.classList.add("active");
        }

        item.addEventListener("click", () => {
            window.location.href = href;
        });
    });
});
