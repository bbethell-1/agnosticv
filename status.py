#!/usr/bin/python3

import time
import requests
import json
from requests.auth import HTTPBasicAuth
from argparse import ArgumentParser
import re
import os
import yaml
from retry.api import retry_call

spioKeyRoot="c1e49027-775a-4545-af94-361b1ed464ba"
spioKey="OAuth " + spioKeyRoot
spioURL="https://api.statuspage.io/v1"
pageDest = "RHDP"


def mkparser():
  parser = ArgumentParser()
  parser.add_argument('--dryrun', help='Make no changes', action="store_true")
  parser.add_argument('--debug', help='DEBUG', action="store_true")
  return parser

def apiCallSPIO(url, op, payload=""):
  #print(op + " " + spioURL + url)
  head = {'Content-Type': 'application/json', 'Authorization': spioKey, 'accept': 'application/json;version=2'}
  if op == "get":
    if url == "/pages":
      response = requests.get(spioURL + url, headers=head)
      obj = response.json()
    else:
      page = 1
      obj = []
      while True:
        urlstr =  spioURL + url + "?page=" + str(page)
        resp = requests.get(urlstr, headers=head)
        if not resp.json():
          break
        else:
          obj = obj + resp.json()
          page += 1
  elif dryrun:
    obj = {}
  else:
    if op == "delete":
      head = { 'Authorization': spioKey}
      obj = requests.delete(spioURL + url, headers=head)
    if op == "put":
      response = retry_call(requests.put, fargs=[spioURL + url], fkwargs={'headers': head, 'data': json.dumps(payload)}, tries=5, delay=1, backoff=2)
      obj = response.json()
    if op == "post":
      response = retry_call(requests.post, fargs=[spioURL + url], fkwargs={'headers': head, 'data': json.dumps(payload)}, tries=5, delay=1, backoff=2)
      obj = response.json()
  #print(response.json())
  if 'error' in obj:
    print("API ERROR:")
    print(obj)
    exit(1)
  else:
    if not dryrun:
      time.sleep(1)
  return obj

parser = mkparser()
args = parser.parse_args()
if args.dryrun:
  dryrun = True
else:
  dryrun = False

if args.debug:
  debug = True
else:
  debug = False

def getAgnosticVcatalog():
  catalog = {}
  agvDir = "/home/bbethell/Github/agnosticv"
  if debug:
    print("Switching to " + agvDir)
  os.chdir(agvDir)
  gitcmd = "git pull 2>/dev/null"
  if debug:
    print("Pulling git repo..")
    gitcmd = "git pull 2>&1"
  try:
    stream = os.popen(gitcmd)
  except:
    print("GIT pull failed to run properly, cannot continue.")
    raise
  if debug:
    print("Running agnosticv binary..")
  try:
    stream = os.popen("agnosticv --list|grep -E 'prod\\.ya?ml'")
  except:
    print("The agnosticv list command failed to run properly, cannot continue.")
    raise
  allCatalogItems = stream.read()
  if not allCatalogItems:
    print("The agnosticv list command returned nill, cannot continue.")
    exit()
  for ci in allCatalogItems.splitlines():
    if debug:
      print("Running agnosticv binary for " + ci)
    try:
      stream = os.popen("agnosticv --merge %s" % (ci))
    except:
      print("The agnosticv merge command failed to run properly, cannot continue.")
      raise
    content = stream.read()
    if not content:
      print("The agnosticv merge command returned nill, cannot continue.")
      exit()
    m = yaml.load(content, Loader=yaml.BaseLoader)
    if '__meta__' in m and 'catalog' in m['__meta__'] and 'namespace' in m['__meta__']['catalog'] and 'babylon-catalog' in m['__meta__']['catalog']['namespace']:
      #if 'disable' in m['__meta__']['catalog'] and m['__meta__']['catalog']['disable']:
      #  continue
      if 'labels' in m['__meta__']['catalog'] and 'Base_Component' in m['__meta__']['catalog']['labels'] and m['__meta__']['catalog']['labels']['Base_Component'] == "False":
        continue
      if 'display_name' in m['__meta__']['catalog'] and 'labels' in m['__meta__']['catalog'] and 'Product_Family' in m['__meta__']['catalog']['labels']:
        productFamily = m['__meta__']['catalog']['labels']['Product_Family']
        if productFamily not in catalog:
          catalog[productFamily] = []
        catalog[productFamily].append(m['__meta__']['catalog']['display_name'])
  return catalog

agVcatalog = getAgnosticVcatalog()
#print(agVcatalog)

allNames = []
for productFamilyName, catalogItems in agVcatalog.items():
  for catalogItem in catalogItems:
    if catalogItem in allNames:
      print("ERROR: Duplicate display_name %s" % catalogItem)
      exit(1)
    else:
      allNames.append(catalogItem)

allComponentGroupList = []
allComponentList = []
componentIDs = {}

pages = apiCallSPIO("/pages", "get")
#print(pages)
spioPageID = ""
for page in pages:
  if page['name'] == pageDest:
    spioPageID = page['id']
    if debug:
      print("Found page %s (%s)" % (page['name'], page['id']) )
    break
if spioPageID == "":
  print("ERROR No such page '%s' found in statuspage.io" % pageDest)
  exit(1)

allComponentGroups = apiCallSPIO("/pages/" + spioPageID + "/component-groups", "get")
for componentGroup in allComponentGroups:
  allComponentGroupList.append(componentGroup['name'])

allComponents = apiCallSPIO("/pages/" + spioPageID + "/components", "get")
for component in allComponents:
  if args.debug:
    print("Existing component: " + component['name'])
  if not component['group']:
    componentGroupID = component['group_id']
    componentID = component['id']
    for componentGroup in allComponentGroups:
      if componentGroup['id'] == componentGroupID:
        allComponentList.append(component['name'])
        componentIDs[componentID] = component['name']
        break

for productFamilyName, catalogItems in agVcatalog.items():
  placeHolderID = ""
  if productFamilyName not in allComponentGroupList:
    if not dryrun:
      print("Creating component group '%s'" % productFamilyName)
      payload = { "component": {"name": "placeholder", "description": "placeholder", "status": "operational", "only_show_if_degraded": False, "showcase": False }}
      phout = apiCallSPIO("/pages/" + spioPageID + "/components", "post", payload)
      placeHolderID = phout['id']
      payload = { "component_group": {
        "components": [ placeHolderID ],
        "name": productFamilyName
        }
      }
      apiCallSPIO("/pages/" + spioPageID + "/component-groups", "post", payload)
    else:
      print("Need to create component group '%s'" % productFamilyName)
    allComponentGroupList.append(productFamilyName)
    allComponentGroups.clear()
    allComponentGroups = apiCallSPIO("/pages/" + spioPageID + "/component-groups", "get")
  for componentGroup in allComponentGroups:
    if componentGroup['name'] == productFamilyName:
      componentGroupID = componentGroup['id']
      break
  for catalogItem in catalogItems:
    if catalogItem not in allComponentList:
      if not dryrun:
        print("Adding catalog item: '%s' to catalog: '%s'" % (catalogItem, productFamilyName))
        payload = { "component": {
            "name": catalogItem,
            "group_id": componentGroupID
          }
        }
        apiCallSPIO("/pages/" + spioPageID + "/components", "post", payload)
      else:
        print("Need to add catalog item: '%s' to catalog: '%s'" % (catalogItem, productFamilyName))
      allComponentList.append(catalogItem)
    else:
      moveTo = ""
      moveFrom = ""
      moveComponentID = ""
      for component in allComponents:
        if component['name'] == catalogItem:
          for componentGroup in allComponentGroups:
            if component['group_id'] == componentGroup['id'] and componentGroup['name'] != productFamilyName:
              if args.debug:
                print("cgid: %s cgname: %s catalogname: %s" % (component['group_id'], componentGroup['name'], productFamilyName ))
              moveTo = productFamilyName
              moveFrom = componentGroup['name']
              moveComponentID = component['id']
              break
          break
      if moveTo != "":
        for componentGroup in allComponentGroups:
          if moveTo == componentGroup['name']:
            if not dryrun:
              print("Moving catalog item '%s' from '%s' to '%s'" % (catalogItem, moveFrom, moveTo))
              payload = { "component": { "group_id": componentGroup['id']} }
              apiCallSPIO("/pages/" + spioPageID + "/components/" + moveComponentID, "put", payload)
            else:
              print("Need to move catalog item '%s' from '%s' to '%s'" % (catalogItem, moveFrom, moveTo))
            break
    if placeHolderID != "":
      if not dryrun:
        print("Deleting placeholder.")
        apiCallSPIO("/pages/" + spioPageID + "/components/" + placeHolderID, "delete")
      else:
        print("Need to delete placeholder.")
      placeHolderID = ""

for component in allComponents:
  componentName = component['name']
  if re.match('^(WEB|EXTERNAL|CLOUD):', componentName) or component['group']:
    continue
  componentID = component['id']
  if not component['group_id']:
    print("WARNING: Component %s is not in a group! Leaving it alone." % component['name'])
    continue
  componentGroupID = component['group_id']
  for componentGroup in allComponentGroups:
    if componentGroup['id'] == componentGroupID:
       componentGroupName = componentGroup['name']
       break
  found = False 
  for productFamilyName, catalogItems in agVcatalog.items():
    if productFamilyName != componentGroupName:
      continue
    for catalogItem in catalogItems:
      if componentName == catalogItem:
        found = True
        break
  if not found:
    if not dryrun:
      print("Deleting catalog item: '%s/%s'" % (componentGroupName, componentName))
      apiCallSPIO("/pages/" + spioPageID + "/components/" + componentID, "delete")
    else:
      print("Need to delete catalog item: '%s/%s'" % (componentGroupName, componentName))

acg = apiCallSPIO("/pages/" + spioPageID + "/component-groups", "get")
for componentGroup in acg:
  if len(componentGroup['components']) == 0:
    if not dryrun:
      print("Deleting empty component group: '%s'" % (componentGroup['name']))
      apiCallSPIO("/pages/" + spioPageID + "/component-groups/" + componentGroup['id'], "delete")
    else:
      print("Need to delete empty component group: '%s'" % (componentGroup['name']))
