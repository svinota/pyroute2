#!/usr/bin/env bash

find docs \
    -name 'aafig-*svg' \
    -exec python util/aafigure_mapper.py docs/aafigure.map '{}' \;
