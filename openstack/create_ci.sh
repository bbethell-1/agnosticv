#!/bin/bash

test=`find . -name NOVELLO_EXAMPLE`

if [ -z "$test" ]
then
  echo "You must be in the agnosticv/openstack directory to run this"
  exit 1
fi


echo -n "Enter name for git branch to create (ex: mybranch-1): ";read gb
echo

git checkout -b $gb

echo -n "Enter name for agnosticV catalog item (ex: NOVELLO_EXAMPLE_ITEM): ";read ci
echo

echo -n "Enter novello converted blueprint name (ex: my-blueprint-bp): ";read bp
echo

echo -n "Enter OPENTLC or RHPDS: ";read en
echo

cp -pr NOVELLO_EXAMPLE $ci

cd $ci
sed -i "s/PLATFORM/$en/" common.yml
sed -i "s/example-bp/$bp/" common.yml
sed -i "s/my-example-blueprint/$bp/" test.yaml
sed -i "s/my-example-blueprint/$bp/" prod.yaml

git add -A

echo "Modify new files as needed then run:"
echo
echo "git commit -a"
echo "git push --set-upstream origin $gb"
echo
echo "Then in the github website, create a PR for this branch"
