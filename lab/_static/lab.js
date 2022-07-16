let context = {};
let base_url = "";

if (window.hostname) {
    base_url = `${window.protocol}//${window.hostname}`
};

let bootstrap = `
import io
import micropip
import sys
from pprint import pprint

await micropip.install("${base_url}/pyroute2.minimal-0.7.1.post3-py3-none-any.whl")

from pyroute2.netlink import nlmsg

def print(data):
    if isinstance(data, nlmsg):
        return pprint(data.dump())
    return pprint(data)

`;

let pre_load = `
sys.stdout = io.StringIO()
`;

let post_load = `
result = sys.stdout.getvalue()
`;


function execute_example(name) {
    let setup = document.getElementById(name + "-setup").value;
    let task = document.getElementById(name + "-task").value;
    let check = document.getElementById(name + "-check").value;

    context.pyodide.runPython(pre_load, { globals: context.namespace });
    context.pyodide.runPython(setup, { globals: context.namespace });
    context.pyodide.runPython(task, { globals: context.namespace });
    context.pyodide.runPython(check, { globals: context.namespace });
    context.pyodide.runPython(post_load, { globals: context.namespace });
    let data = context.namespace.get("result");
    document.getElementById(name + "-data").innerHTML = "<pre>" + data + "</pre>";
}

function clear_example_output(name) {
    document.getElementById(name + "-data").innerHTML = "";
}

async function main() {
    let pyodide = await loadPyodide();
    let namespace = pyodide.globals.get("dict")();
    await pyodide.loadPackage("micropip");
    await pyodide.runPythonAsync(bootstrap, { globals: namespace });
    context.pyodide = pyodide
    context.namespace = namespace
    document.getElementById("load").innerHTML = "loaded";
    Array.from(
        document.getElementsByClassName("loading")
    ).map(function(x) {
        x.removeAttribute("readonly");
        x.className = "loaded";
    });
};


window.addEventListener("load", main);
