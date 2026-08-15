/*
 * Swaps a CAPTCHA challenge in place.
 *
 * The button ships hidden and is revealed here, so a visitor without
 * JavaScript never sees a control that cannot work. Clicks are handled by
 * delegation on the document, which is what makes a widget that was itself
 * just swapped in keep working with nothing to re-attach.
 */
(function () {
    if (window.__captchaKitRefresh) {
        return;
    }
    window.__captchaKitRefresh = true;

    function reveal(root) {
        var buttons = (root || document).querySelectorAll("[data-captcha-refresh]");
        Array.prototype.forEach.call(buttons, function (button) {
            button.hidden = false;
        });
    }

    function announce(widget) {
        var status = widget.querySelector("[data-captcha-status]");
        if (status) {
            status.textContent = status.getAttribute("data-captcha-message") || "";
        }
    }

    document.addEventListener("click", function (event) {
        var button = event.target.closest && event.target.closest("[data-captcha-refresh]");
        if (!button) {
            return;
        }
        var widget = button.closest("[data-captcha]");
        var url = widget && widget.getAttribute("data-captcha-url");
        if (!url) {
            return;
        }
        event.preventDefault();
        button.disabled = true;
        button.setAttribute("aria-busy", "true");

        fetch(url, { credentials: "same-origin", headers: { "X-Requested-With": "fetch" } })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error(response.status);
                }
                return response.text();
            })
            .then(function (html) {
                var holder = document.createElement("div");
                holder.innerHTML = html;
                /* Only the widget is taken from the reply; the <script> tag it
                 * carries is dropped, which is what keeps this file from being
                 * evaluated a second time. */
                var fresh = holder.querySelector("[data-captcha]");
                if (!fresh) {
                    throw new Error("unexpected reply");
                }
                widget.replaceWith(fresh);
                reveal(fresh);
                announce(fresh);
                var answer = fresh.querySelector("input[type='text']");
                if (answer) {
                    answer.focus();
                }
            })
            .catch(function () {
                button.disabled = false;
                button.removeAttribute("aria-busy");
            });
    });

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", function () {
            reveal();
        });
    } else {
        reveal();
    }
})();
