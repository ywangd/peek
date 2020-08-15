#!/usr/bin/env bash

# Shell integration for peek to support simply copy/paste to execute examples
# from documentation.

Payload="$*"
while read line; do
    if [[ -z "$line" ]]; then
        break
    fi
    Payload="$Payload\n$line"
done

echo -e $Payload | peek
