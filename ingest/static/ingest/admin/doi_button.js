document.addEventListener("DOMContentLoaded", function () {

    // ── Preference toggle: "Open DataCite preview after minting" ──
    // Persisted in localStorage; defaults to true (open on success).
    function isPreviewEnabled() {
        var v = localStorage.getItem("bil-doi-preview");
        return v === null ? true : v === "true";
    }

    function injectPreferenceToggle() {
        // Only inject on admin pages that have at least one Create DOI button.
        if (!document.querySelector(".bil-doi-btn")) return;
        if (document.getElementById("bil-doi-preview-toggle")) return;

        var toggle = document.createElement("label");
        toggle.id = "bil-doi-preview-bar";
        toggle.style.cssText =
            "cursor:pointer; display:inline-flex; align-items:center; gap:.4em;" +
            " padding:.35em .65em; border:1px solid rgba(128,128,128,.35);" +
            " border-radius:4px; font-size:.82em; opacity:.85; margin-right:.5em;" +
            " white-space:nowrap;";
        toggle.innerHTML =
            '<input type="checkbox" id="bil-doi-preview-toggle"' +
            (isPreviewEnabled() ? " checked" : "") +
            ' style="width:1em; height:1em; accent-color:#1a73e8; cursor:pointer; margin:0;">' +
            '<span>Open DataCite preview after minting</span>';

        // Try to place it inline with the search + filters row so it lives in
        // the toolbar area. Fall back to the changelist top as needed.
        var filtersBtn =
            document.querySelector('[data-filter-button], [x-data*="filter"], .changelist-filter, #changelist-filter');
        var searchForm = document.querySelector("#toolbar, #changelist-search, form#changelist-search");
        var anchor = filtersBtn || searchForm;

        if (anchor && anchor.parentNode) {
            anchor.parentNode.insertBefore(toggle, anchor);
        } else {
            var host =
                document.querySelector("#changelist") ||
                document.querySelector("#content-main") ||
                document.body;
            host.insertBefore(toggle, host.firstChild);
        }

        document
            .getElementById("bil-doi-preview-toggle")
            .addEventListener("change", function (e) {
                localStorage.setItem("bil-doi-preview", e.target.checked);
            });
    }

    injectPreferenceToggle();

    // ── Create DOI button click handler ──
    document.addEventListener("click", function (e) {
        const btn = e.target.closest(".bil-doi-btn");
        if (!btn) return;

        const bilId = btn.dataset.bilId;
        const url = btn.dataset.url;

        if (!confirm(`Create DOI for BIL_ID: ${bilId}?`)) return;

        btn.disabled = true;
        btn.textContent = "Creating…";

        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCsrfToken(),
            },
            body: JSON.stringify({ bildid: bilId, action: "publish" }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function ({ ok, data }) {
                if (ok && data.success) {
                    btn.outerHTML = '<span style="color:green;font-weight:600;">✅ DOI Created</span>';
                    if (isPreviewEnabled() && data.doi_url) {
                        window.open(data.doi_url, "_blank");
                    } else {
                        alert("DOI " + data.doi + " created successfully.");
                    }
                } else {
                    alert("DOI creation failed:\n" + (data.error || JSON.stringify(data)));
                    btn.disabled = false;
                    btn.textContent = "Create DOI";
                }
            })
            .catch(function (err) {
                alert("Request error: " + err);
                btn.disabled = false;
                btn.textContent = "Create DOI";
            });
    });

    function getCsrfToken() {
        const match = document.cookie.split("; ").find(function (c) { return c.startsWith("csrftoken="); });
        return match ? match.split("=")[1] : "";
    }
});
