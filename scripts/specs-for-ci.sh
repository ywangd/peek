#!/usr/bin/env bash

if [[ -n "$MULE_TOKEN" ]]; then
    curl -L --remote-name -H 'Accept: application/vnd.github.v3.raw' -H "Authorization: token $MULE_TOKEN" https://api.github.com/repos/ywangd/mule/contents/kibana-7.8.1-spec-files.tgz
    tar -C peek -zxvf kibana-7.8.1-spec-files.tgz

    curl -L --remote-name -H 'Accept: application/vnd.github.v3.raw' -H "Authorization: token $MULE_TOKEN" https://api.github.com/repos/ywangd/mule/contents/schema-8.2.tgz
    tar -C peek -zxvf schema-8.2.tgz
fi
