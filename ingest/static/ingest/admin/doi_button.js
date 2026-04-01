(function () {
    function getCookie(name) {
        const value = `; ${document.cookie}`;
        const parts = value.split(`; ${name}=`);
        if (parts.length === 2) return parts.pop().split(";").shift();
        return "";
    }

    document.addEventListener("click", function (e) {
        const btn = e.target.closest(".bil-doi-btn");
        if (!btn) return;

        e.preventDefault();
        e.stopPropagation();

        const bilId = btn.getAttribute("data-bil-id");
        const url = btn.getAttribute("data-url");

        if (!confirm(`Are you sure you want to create a DOI for ${bilId}?`)) return;

        btn.disabled = true;
        btn.textContent = "Creating…";

        fetch(url, {
            method: "POST",
            headers: {
                "Content-Type": "application/json",
                "X-CSRFToken": getCookie("csrftoken"),
            },
            body: JSON.stringify({ bildid: bilId, action: "draft" }),
            credentials: "same-origin",
        })
            .then((r) => r.json().then((d) => ({ ok: r.ok, status: r.status, d })))
            .then(({ ok, d, status }) => {
                if (!ok) throw new Error(d?.error || `Request failed (${status})`);

                alert("✅ DOI successfully created!");

                if (d.doi_url) window.open(d.doi_url, "_blank", "noopener,noreferrer");
                window.location.reload();
            })
            .catch((err) => {
                alert(`❌ Error: ${err.message}`);
                btn.disabled = false;
                btn.textContent = "Create DOI";
            });
    });
})();