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

echo -n "Enter env type (ex: ocp-workshop): ";read envtype
echo

echo -n "Enter OPENTLC or RHPDS: ";read en
echo

echo -n "Enter git tag: ";read gittag
echo

cp -pr NOVELLO_EXAMPLE $ci
cat NOVELLO_EXAMPLE/common.yml |grep -v project > $ci/common.yml

cd $ci
if [ -x /usr/local/bin/gsed ]
then
  # For OSX
  sed=/usr/local/bin/gsed
else
  sed=sed
fi
$sed -i "s/PLATFORM/$en/" common.yml
$sed -i "s/osp-migration/$envtype/" common.yml
$sed -i "s/my-example-blueprint/$gittag/" test.yaml
$sed -i "s/my-example-blueprint/$gittag/" prod.yaml

git add -A

echo "Modify new files as needed then run:"
echo
echo "git commit -a"
echo "git push --set-upstream origin $gb"
echo
echo "Then in the github website, create a PR for this branch"
echo
echo "After creating the PR use"
echo "git checkout master;git pull"
echo "to get back to the master branch."
