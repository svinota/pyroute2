window.addEventListener("load", function() {
    Array.from(
        document.getElementsByTagName("img")
    ).map(
        function(img) {
            img.removeAttribute("width");
            img.removeAttribute("height");
        }
    )
})
