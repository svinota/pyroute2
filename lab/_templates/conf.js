const pyroute2_distfile = "{{ distfile }}";
let pyroute2_base_url = "";

if (window.hostname) {
    pyroute2_base_url = `${window.protocol}//${window.hostname}`;
};
