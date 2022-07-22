
const pyroute2_lab_context = {
    log_buffer: [],
    log_size_max: 16,
    pyodide: null,
    python_namespace: null,
    python_loaded: false,
    bootstrap: `
import io
import micropip
import sys
import pprint
import builtins

await micropip.install("${pyroute2_base_url}/${pyroute2_distfile}")

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
`,
    exercise_pre: "sys.stdout = io.StringIO()",
    exercise_post: "result = sys.stdout.getvalue()",
};


function pyroute2_log_record(argv) {
    let ctime = new Date();
    pyroute2_lab_context.log_buffer.push([ctime, argv]);
    if (pyroute2_lab_context.log_buffer.length > pyroute2_lab_context.log_size_max) {
        pyroute2_lab_context.log_buffer.shift();
    };
    dmesg = document.getElementById("dmesg");
    if (dmesg) {
        let log_output = "";
        pyroute2_lab_context.log_buffer.map(function (x) {
            log_output += `<span class="pyroute2-log-record">${x[1]}</span>`;
        });
        dmesg.innerHTML = log_output;
    };
};

function pyroute2_escape_untrusted(data) {
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

async function pyroute2_execute_example(name) {
    let setup = document.getElementById(name + "-setup").value;
    let task = document.getElementById(name + "-task").value;
    let check = document.getElementById(name + "-check").value;
    let data = "";
    let namespace = { globals: pyroute2_lab_context.python_namespace };
    let pyodide = pyroute2_lab_context.pyodide;
    if (!pyroute2_lab_context.python_loaded) {
        // if python is not loaded yet, wait a second...
        await new Promise(resolve => setTimeout(resolve, 1000));
        // and try again
        await pyroute2_execute_example(name);
        return;
    } else {
        try {
            pyodide.runPython(pyroute2_lab_context.exercise_pre, namespace);
            pyodide.runPython(setup, namespace);
            pyodide.runPython(task, namespace);
            pyodide.runPython(check, namespace);
            pyodide.runPython(pyroute2_lab_context.exercise_post, namespace);
            data = pyroute2_lab_context.python_namespace.get("result");
        } catch(exception) {
            data = `${exception}`
        };
    };
    // recode untrusted output
    data = pyroute2_escape_untrusted(data)
    document.getElementById(name + "-data").innerHTML = `<pre>${data}</pre>`;
}

function pyroute2_clear_example_output(name) {
    document.getElementById(name + "-data").innerHTML = "";
}

async function pyroute2_lab_main() {
    if (!document.getElementById("dmesg")) {
        return;
    };
    pyroute2_log_record("Booting the system, be patient");
    pyroute2_log_record("Starting python");
    let pyodide = null;
    let namespace = null;
    // try to load python
    try {
        pyodide = await loadPyodide();
        namespace = pyodide.globals.get("dict")();
        await pyodide.loadPackage("micropip");
        await pyodide.runPythonAsync(pyroute2_lab_context.bootstrap, { globals: namespace });
    } catch(exception) {
        pyroute2_log_record(`<pre>${exception}</pre>`);
        pyroute2_log_record("Please report this bug to the project <a href='https://github.com/svinota/pyroute2/issues'>bug tracker</a>, and don't forget to specify your browser.");
        return;
    };
    // setup global context
    pyroute2_lab_context.pyodide = pyodide;
    pyroute2_lab_context.python_namespace = namespace;
    // reset log
    pyroute2_lab_context.log_buffer.length = 0;
    pyroute2_lab_context.python_loaded = true;
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
    pyroute2_log_record(`System loaded [ ${pyroute2_distfile} ]`);
};

window.addEventListener("load", pyroute2_lab_main);
