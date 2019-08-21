#!/bin/bash

# Produce output suitable for babylon 
echo environment_parameters:
./merge.sh "$@"  | egrep -v "^\-\-\-|\#\ \/" | sed 's/^/  /'
