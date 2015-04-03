BEGIN {
    conf["VERSION"] = version
    conf["RELEASE"] = release
    conf["SETUPLIB"] = setuplib
}

{
    while (1) {
        # pick one variable
        variable = gensub(/.*@([^@]*)@.*/,"\\1",1)
        # no more variables left
        if (variable == $0) break
        # value lookup:
        value = conf[variable]
        # substitute the variable
        gsub("@"variable"@", value)
    }
    print $0
}
