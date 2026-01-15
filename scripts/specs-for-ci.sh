#!/usr/bin/env bash

curl -L --remote-name https://raw.githubusercontent.com/ywangd/mule/main/kibana-7.8.1-spec-files.tgz
tar -C peek -zxvf kibana-7.8.1-spec-files.tgz

curl -L --remote-name https://raw.githubusercontent.com/ywangd/mule/main/schema-8.2.tgz
tar -C peek -zxvf schema-8.2.tgz
mv peek/specs/schema-8.2/schema.json peek/specs/schema.json
