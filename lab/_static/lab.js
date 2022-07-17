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

const bootstrap = `
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

const exercise_pre = `
sys.stdout = io.StringIO()
`;

const exercise_post = `
result = sys.stdout.getvalue()
`;

function escape_untrusted(data) {
    return data.replace(/[<>&'"]/g, function (x) {
        switch (x) {
            case '<': return '&lt;';
            case '>': return '&gt;';
            case '&': return '&amp;';
            case "'": return '&apos;';
            case '"': return '&quot;';
        }
    });
}

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
            context.pyodide.runPython(exercise_pre, { globals: context.namespace });
            context.pyodide.runPython(setup, { globals: context.namespace });
            context.pyodide.runPython(task, { globals: context.namespace });
            context.pyodide.runPython(check, { globals: context.namespace });
            context.pyodide.runPython(exercise_post, { globals: context.namespace });
            data = context.namespace.get("result");
        } catch(exception) {
            data = `${exception}`
        };
    };
    // recode untrusted output
    data = escape_untrusted(data)
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
    let pyodide = null;
    let namespace = null;
    // try to load python
    try {
        pyodide = await loadPyodide();
        namespace = pyodide.globals.get("dict")();
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(bootstrap, { globals: namespace });
    } catch(exception) {
        console.log(`<pre>${exception}</pre>`);
        console.log("Please report this bug to the project <a href='https://github.com/svinota/pyroute2/issues'>bug tracker</a>, and don't forget to specify your browser.");
        return;
    };
    // setup global context
    context.pyodide = pyodide;
    context.namespace = namespace;
    // reset log
    log_buffer.length = 0;
    python_loaded = true;
    // make exercises visible
    Array.from(
        document.getElementsByTagName("section")
    ).map(function(x) {
        x.style['display'] = 'block';
    });
    // unlock code blocks
    Array.from(
        document.getElementsByClassName("loading")
    ).map(function(x) {
        x.removeAttribute("readonly");
        x.className = "loaded";
    });
    console.log(`System loaded [ ${distfile} ]`);
};


window.addEventListener("load", main);
