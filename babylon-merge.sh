#!/bin/bash

# Produce output suitable for babylon 
echo job_vars:
./merge.sh "$@"  | egrep -v "^\-\-\-|\#\ \/" | sed 's/^/  /'
