const log = console.log;
const log_buffer = [];
const log_size_max = 16;
console.log = (...argv) => {
    let ctime = new Date();
    log.apply(console, argv);
    log_buffer.push([ctime, argv]);
    if (log_buffer.length > log_size_max) {
        log_buffer.shift();
    };
    dmesg = document.getElementById("dmesg");
    if (dmesg) {
        let log_output = "";
        log_buffer.map(function (x) {
            log_output += `<span class="log_record">${x[1]}</span>`;
        });
        dmesg.innerHTML = log_output;
    };
};

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

    log_buffer.length = 0;
    try {
        context.pyodide.runPython(pre_load, { globals: context.namespace });
        context.pyodide.runPython(setup, { globals: context.namespace });
        context.pyodide.runPython(task, { globals: context.namespace });
        context.pyodide.runPython(check, { globals: context.namespace });
        context.pyodide.runPython(post_load, { globals: context.namespace });
        let data = context.namespace.get("result");
        document.getElementById(name + "-data").innerHTML = "<pre>" + data + "</pre>";
        console.log('Check successful');
    } catch(exception) {
        console.log(`Exception <pre>${exception}</pre>`);
    };
}

function clear_example_output(name) {
    document.getElementById(name + "-data").innerHTML = "";
}

async function main() {
    console.log("Loading Python, be patient");
    let pyodide = await loadPyodide();
    let namespace = pyodide.globals.get("dict")();
    await pyodide.loadPackage("micropip");
    await pyodide.runPythonAsync(bootstrap, { globals: namespace });
    context.pyodide = pyodide;
    context.namespace = namespace;
    log_buffer.length = 0;
    console.log("System loaded");
    Array.from(
        document.getElementsByClassName("loading")
    ).map(function(x) {
        x.removeAttribute("readonly");
        x.className = "loaded";
    });
};


window.addEventListener("load", main);
