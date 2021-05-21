/^[[:space:]]+pr2modules/ {
    next
}

/^[[:space:]]+[[:alpha:]]/ {
    deps[$1][key]++
}

/^[[:alpha:]]+/ {
    key = gensub(":", "", "g", $1)
}

END {
    for (i in deps) {
        print(i);
        for (k in deps[i]) {
            print("\t"k);
        };
    };
}
