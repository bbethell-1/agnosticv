#!/bin/bash

types="red green orange blue pink prod ilt test dev"

if [ -z "$1" ]
then
  env=prod
else
  env=$1
fi

echo "CI,SCHEDULER,SECRET"
for dir in `find * -type d -maxdepth 1`
do
  if [ ! -f ${dir}/${env}.yaml ]
  then
    continue
  fi
  tst=`grep "scheduler:" ${dir}/${env}.yaml`
  echo -n "${env},${dir},"
  if [ -n "$tst" ]
  then
    tst2=`grep "enable: true" ${dir}/${env}.yaml`
    if [ -n "$tst2" ]
    then
      echo -n "enabled"
    else
      echo -n "disabled"
    fi
  else
    echo -n "N/A"
  fi
  echo -n ","
  for typ in $types
  do
    tst=`grep "openstack-${typ}" ${dir}/${env}.yaml`
    if [ -n "$tst" ]
    then
      echo -n "${typ} "
    fi
  done
  echo
done
