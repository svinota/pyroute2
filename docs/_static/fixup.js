window.addEventListener("load", function() {
    Array.from(
        document.getElementsByTagName("img")
    ).map(
        function(img) {
            img.removeAttribute("width");
            img.removeAttribute("height");
        }
    );

    if (!document.getElementById("fold-sources")) return;

    Array.from(
        document.getElementsByClassName("highlight-python notranslate")
    ).map(
        function(node) {
            let div_id = Math.round(Math.random() * 10000);
            let parent_node = node.parentElement;
            let function_node = node.firstChild.firstChild.children[2];
            if (function_node.className != 'nf') return;
            let function_name = function_node.textContent;
            div_clickable = document.createElement("div");
            div_switchable = document.createElement("div");
            source_header = document.createElement("div");
            source_title = document.createElement("span");
            source_hint = document.createElement("span");
            source_title.className = "source-title";
            source_title.textContent = function_name + "()";
            source_hint.className = "source-hint";
            source_hint.textContent = ": (click to toggle the source)";
            source_header.appendChild(source_title);
            source_header.appendChild(source_hint);
            div_clickable.appendChild(source_header);
            div_clickable.appendChild(div_switchable);
            div_clickable.className = "source-switch";
            div_clickable.setAttribute("onclick", "source_toggle(" + div_id + ")");
            parent_node.replaceChild(div_clickable, node);
            div_switchable.setAttribute("class", "hidden");
            div_switchable.setAttribute("id", div_id);
            div_switchable.appendChild(node);
        }
    );
});

function source_toggle(div_id) {
    node = document.getElementById(div_id);
    if (node.className == "hidden") {
        node.className = "source-view";
    } else {
        node.className = "hidden";
    };
};
