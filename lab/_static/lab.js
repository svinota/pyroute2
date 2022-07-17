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
let python_loaded = false;

if (window.hostname) {
    base_url = `${window.protocol}//${window.hostname}`
};

let bootstrap = `
import io
import micropip
import sys
import pprint
import builtins

await micropip.install("${base_url}/${distfile}")

from pyroute2.netlink import nlmsg


def print(*argv, end='\\n'):
    for data in argv:
        if isinstance(data, nlmsg):
            pprint.pprint(data.dump())
        elif isinstance(data, (str, int, float)):
            builtins.print(data, end='')
        else:
            pprint.pprint(data)
        builtins.print(' ', end='')
    builtins.print(end=end)
`;

let pre_load = `
sys.stdout = io.StringIO()
`;

let post_load = `
result = sys.stdout.getvalue()
`;

async function execute_example(name) {
    let setup = document.getElementById(name + "-setup").value;
    let task = document.getElementById(name + "-task").value;
    let check = document.getElementById(name + "-check").value;
    let data = "";
    if (!python_loaded) {
        await new Promise(resolve => setTimeout(resolve, 1000));
        await execute_example(name);
        return;
    } else {
        try {
            context.pyodide.runPython(pre_load, { globals: context.namespace });
            context.pyodide.runPython(setup, { globals: context.namespace });
            context.pyodide.runPython(task, { globals: context.namespace });
            context.pyodide.runPython(check, { globals: context.namespace });
            context.pyodide.runPython(post_load, { globals: context.namespace });
            data = context.namespace.get("result");
        } catch(exception) {
            data = `${exception}`
        };
    };
    document.getElementById(name + "-data").innerHTML = `<pre>${data}</pre>`;
}

function clear_example_output(name) {
    document.getElementById(name + "-data").innerHTML = "";
}

async function main() {
    if (!document.getElementById("dmesg")) {
        return;
    };
    console.log("Booting the system, be patient");
    console.log("Starting python");
    let pyodide = await loadPyodide();
    let namespace = pyodide.globals.get("dict")();
    await pyodide.loadPackage("micropip");
    await pyodide.runPythonAsync(bootstrap, { globals: namespace });
    context.pyodide = pyodide;
    context.namespace = namespace;
    log_buffer.length = 0;
    python_loaded = true;
    console.log(`System loaded [ ${distfile} ]`);
    Array.from(
        document.getElementsByTagName("section")
    ).map(function(x) {
        x.style['display'] = 'block';
    });
    Array.from(
        document.getElementsByClassName("loading")
    ).map(function(x) {
        x.removeAttribute("readonly");
        x.className = "loaded";
    });
};


window.addEventListener("load", main);
