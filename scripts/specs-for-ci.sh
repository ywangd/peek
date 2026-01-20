#!/usr/bin/env bash

curl -L --remote-name https://raw.githubusercontent.com/ywangd/mule/main/schema-8.2.tgz
tar -C peek -zxvf schema-8.2.tgz
mv peek/specs/schema-8.2/schema.json peek/specs/schema.json
