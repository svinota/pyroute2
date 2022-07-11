window.addEventListener("load", function () {
  const images = document.getElementsByTagName("img")
  for (let i = 0; i < images.length; i++) {
      images[i].removeAttribute("width");
      images[i].removeAttribute("height");
  }
})
