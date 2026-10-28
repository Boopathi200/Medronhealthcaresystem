document.addEventListener("DOMContentLoaded", () => {
    const categorySection = document.querySelector(".home-categories");
    const categoryCards = categorySection?.querySelectorAll(".home-category-card");
    const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    if (categorySection && categoryCards?.length && "IntersectionObserver" in window && !reducedMotion) {
        const categoryObserver = new IntersectionObserver(entries => {
            entries.forEach(entry => {
                if (!entry.isIntersecting) {
                    return;
                }

                const card = entry.target;
                const cardIndex = Array.from(categoryCards).indexOf(card) % 6;
                card.style.setProperty("--category-reveal-delay", `${cardIndex * 90}ms`);
                card.classList.add("is-visible");
                categoryObserver.unobserve(card);
                window.setTimeout(() => {
                    card.style.removeProperty("--category-reveal-delay");
                }, 900 + cardIndex * 90);
            });
        }, { threshold: 0.15 });

        categorySection.classList.add("is-observing");
        categoryCards.forEach(card => categoryObserver.observe(card));
    }

    const menuButton = document.querySelector(".menu-toggle");
    const navigation = document.querySelector("#nav");

    if (menuButton && navigation) {
        menuButton.addEventListener("click", () => {
            const isOpen = navigation.classList.toggle("open");
            menuButton.setAttribute("aria-expanded", String(isOpen));
        });
    }

    const modal = document.querySelector("#productModal");
    const popup = modal?.querySelector(".product-popup");
    const popupImage = modal?.querySelector("#popupImage");
    const popupName = modal?.querySelector("#popupName");
    const popupCategory = modal?.querySelector("#popupCategory");
    const popupDescription = modal?.querySelector("#popupDescription");
    const popupSpecifications = modal?.querySelector("#popupSpecifications");
    const popupWhatsapp = modal?.querySelector("#popupWhatsapp");
    const details = modal?.querySelector("#typedDetails");

    if (!modal || !popup || !popupImage || !popupName || !popupCategory || !popupWhatsapp || !details) {
        return;
    }

    let typingTimer;
    let previousFocus;
    let previousBodyOverflow;

    const closeProduct = () => {
        if (!modal.classList.contains("show")) {
            return;
        }

        modal.classList.remove("show");
        modal.setAttribute("aria-hidden", "true");
        document.body.style.overflow = previousBodyOverflow;
        window.clearInterval(typingTimer);
        previousFocus?.focus();
    };

    const openProduct = card => {
        const { name, category, image, whatsappUrl } = card.dataset;
        if (!name || !category || !image || !whatsappUrl) {
            return;
        }

        window.clearInterval(typingTimer);
        details.replaceChildren();
        popupName.textContent = name;
        popupCategory.textContent = category;
        popupImage.src = image;
        popupImage.alt = name;
        popupWhatsapp.href = whatsappUrl;
        if (popupDescription) {
            popupDescription.textContent = card.dataset.description || "";
            popupDescription.hidden = !popupDescription.textContent;
        }
        if (popupSpecifications) {
            popupSpecifications.textContent = card.dataset.specifications || "";
            popupSpecifications.hidden = !popupSpecifications.textContent;
        }
        previousFocus = card;
        previousBodyOverflow = document.body.style.overflow;
        document.body.style.overflow = "hidden";
        modal.classList.add("show");
        modal.setAttribute("aria-hidden", "false");
        popup.focus();

        const lines = [
            "Contact our team for specifications and availability."
        ];
        let lineIndex = 0;
        let characterIndex = 0;
        let currentLine;

        typingTimer = window.setInterval(() => {
            if (lineIndex >= lines.length) {
                window.clearInterval(typingTimer);
                return;
            }

            if (!currentLine) {
                currentLine = document.createElement("p");
                details.appendChild(currentLine);
            }

            currentLine.textContent += lines[lineIndex].charAt(characterIndex);
            characterIndex += 1;

            if (characterIndex >= lines[lineIndex].length) {
                lineIndex += 1;
                characterIndex = 0;
                currentLine = null;
            }
        }, 28);
    };

    document.addEventListener("click", event => {
        const target = event.target;
        if (!(target instanceof Element)) {
            return;
        }

        const card = target.closest(".product-card[data-name]");
        if (card) {
            openProduct(card);
            return;
        }

        if (target === modal || target.closest("[data-close-product]")) {
            closeProduct();
        }
    });

    document.addEventListener("keydown", event => {
        if (event.key === "Escape") {
            closeProduct();
            return;
        }

        const target = event.target;
        if (!(target instanceof Element) || !target.matches(".product-card[data-name]")) {
            return;
        }

        if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            openProduct(target);
        }
    });
});
