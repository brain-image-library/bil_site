document.addEventListener("DOMContentLoaded", function () {
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
            body: JSON.stringify({ bildid: bilId, action: "draft" }),
        })
            .then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
            .then(function ({ ok, data }) {
                if (ok && data.success) {
                    btn.outerHTML = '<span style="color:green;font-weight:600;">✅ DOI Created</span>';
                    if (data.doi_url) {
                        window.open(data.doi_url, '_blank');
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
