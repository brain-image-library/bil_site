document.addEventListener("DOMContentLoaded", function () {
    let table = document.querySelector("#result_list"); // Find the Django Admin table

    if (table) {
        // Create a new div for the fixed horizontal scrollbar
        let scrollDiv = document.createElement("div");
        scrollDiv.className = "fixed-scrollbar";

        // Create an inner div that will act as the scrollbar track
        let scrollTrack = document.createElement("div");
        scrollTrack.className = "scroll-track";

        scrollDiv.appendChild(scrollTrack);
        document.body.appendChild(scrollDiv); // Append to body so it's always visible

        // Sync the new scrollbar width with the table
        scrollTrack.style.width = table.scrollWidth + "px";

        // When the scrollbar is moved, scroll the table horizontally
        scrollDiv.addEventListener("scroll", function () {
            table.parentElement.scrollLeft = scrollDiv.scrollLeft;
        });

        // When the table is scrolled, sync the custom scrollbar
        table.parentElement.addEventListener("scroll", function () {
            scrollDiv.scrollLeft = table.parentElement.scrollLeft;
        });
    }
});