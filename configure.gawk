BEGIN {
    conf["VERSION"] = version
    conf["RELEASE"] = release
    conf["alt", "PACKAGER"] = "Peter V. Saveliev <peet@altlinux.org>"
    conf["rh", "PACKAGER"] = "Peter V. Saveliev <peter@svinota.eu>"
}

{
    while (1) {
        # pick one variable
        variable = gensub(/.*@([^@]*)@.*/,"\\1",1)
        # no more variables left
        if (variable == $0) break
        # value lookup:
        if (conf[flavor, variable]) {
            # dist-specific
            value = conf[flavor, variable]
        } else {
            # common variables
            value = conf[variable]
        }
        # substitute the variable
        gsub("@"variable"@", value)
    }
    print $0
}
