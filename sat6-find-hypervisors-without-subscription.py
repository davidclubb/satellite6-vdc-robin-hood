#!/usr/bin/python
#
# This script checks all the registered hypervisors 
# if sub_attached:
#    if virtual_guests > 0:
#        all fine
#    else:
#        this host consumes sub for no reason
#
#else:
#    if virtual_guests > 0:
#        this host needs a vdc sub
#    else:
#        all fine

import json
import sys
import re
import argparse
import socket

try:
    import requests
except ImportError:
    print "Please install the python-requests module."
    sys.exit(-1)
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

parser = argparse.ArgumentParser(description='sat6-add-to-host-collection.py')
parser.add_argument('-v', '--verbose' , action="store_true", dest='verbose',  help='Be verbose')
parser.add_argument('-a', '--take-action' , action="store_false", dest='noop',  help='Take action and reorganize VDC subscriptions. If not specified, script will only display the changes it would make.')
args =parser.parse_args()

org_name = "Default Organization"
hostname = "localhost"
username = "admin"
password = "password"

api = "https://" + hostname + "/api/"
katello_api = "https://" + hostname + "/katello/api/"
post_headers = {'content-type': 'application/json'}
ssl_verify = False


# Take from these
unnecessary_consumers = []
# And give to these
unentitled = []

def get_json(location):
    """
    Performs a GET using the passed url location
    """
    try:
        r = requests.get(location, auth=(username, password), verify=ssl_verify)
    except requests.ConnectionError, e:
        print "Couldn't connect to the API, check connection or url"
        print e
        sys.exit(1)
    return r.json()


def post_json(location, json_data):
    """
    Performs a POST and passes the data to the url location
    """
    try:
        result = requests.post(location,
                            data=json_data,
                            auth=(username, password),
                            verify=ssl_verify,
                            headers=post_headers)

    except requests.ConnectionError, e:
        print "Couldn't connect to the API, check connection or url"
        print e
        sys.exit(1)
    return result.json()

def put_json(location, json_data):
    """
    Performs a PUT and passes the data to the url location
    """

    result = requests.put(location,
                            data=json_data,
                            auth=(username, password),
                            verify=ssl_verify,
                            headers=post_headers)
def main():
    """
    Main method that gets organizations, hosts and host collections
    and them adds the host to the host collections specified 
    """

    orgs = get_json(katello_api + "organizations/")
    for org in orgs["results"]:
        if org['name'] == org_name:
           org_id = org['id']
           print "Organization " + org_name + " has ID " + str(org['id']) + "\n"

    try:
        org_id
    except NameError:
        print "Organization " + org_name + " does not exist. Exiting..." 
        exit(1)

    hypervisors = get_json(api + "organizations/" + str(org_id) + "/hosts?search=name+~+virt-who&per_page=1000")
    count = 0
    for hypervisor in hypervisors["results"]:
        guests = []
        hyper_hash = {}
        details = get_json(api + "hosts/" + str(hypervisor["id"]))
        if details["subscription_facet_attributes"]["virtual_guests"]:
            has_guests = True
        else:
            has_guests = False
        
        hypervisor_subscription_json = get_json(api + "hosts/" + str(hypervisor["id"]) + "/subscriptions")
        if hypervisor_subscription_json["total"] != 0:
            hypervisor_subscription_name = hypervisor_subscription_json["results"][0]["name"]
            if "Virtual Datacenter" in hypervisor_subscription_name:
                sub_used = True
        else:
            sub_used = False
        
        if sub_used:
            if has_guests:
                status = "Good"
                if args.verbose:
                    guests.append(hypervisor_subscription_name)
                    for virtual_guest in details["subscription_facet_attributes"]["virtual_guests"]:
                        guests.append(virtual_guest["name"])
            else:
                status="Hypervisor consumes a subscription for no reason"

                hyper_hash['host'] = hypervisor
                hyper_hash['sub']  = hypervisor_subscription_json["results"][0]
                unnecessary_consumers.append(hyper_hash)

                if args.verbose:
                    guests.append(hypervisor_subscription_name)
        else:
            if has_guests:
                status="Hypervisor has guests but no subscription"
                hyper_hash['host'] = hypervisor
                hyper_hash['sub']  = hypervisor_subscription_json["results"]
                unentitled.append(hyper_hash)
            else:
                status="No guests and no subscription"
        print hypervisor["name"] + ", id: " + str(hypervisor["id"]) +" | Status: " + status 
        if args.verbose:
            for guest in guests:
                print "|-"+ guest

    print ""
    print ""
    print str(len(unnecessary_consumers)) + " hypervisors consume a VDC while not having any RHEL Content Hosts on them"
    for hypervisor in unnecessary_consumers:
        print hypervisor['host']['name']
    print ""
    print str(len(unentitled)) + " hypervisors has RHEL Content Hosts on them but no VDC sub assigned"
    for hypervisor in unentitled:
        print hypervisor['host']['name']

    print ""
    max_iter = min(len(unentitled), len(unnecessary_consumers))
    print "DEBUG: max iteration " + str(max_iter)

    print "Will transfer the subscriptions from " +  str(len(unnecessary_consumers)) + " hosts to unentitled ones"
    if len(unentitled) > len(unnecessary_consumers):
        print "More unentitled hypervisors than there are subscriptions that we can free up"
        print "Some unentitled hosts will not get a subscription"

    i = 0
    while i < max_iter:
        sub_hash = json.dumps({
        "subscriptions": {
            "id": unnecessary_consumers[i]['sub']['id'],
            "quantity": 1
            }
        })
        print "Taking subscription from " + unnecessary_consumers[i]['host']['name']
        print " and gives it to " + unentitled[i]['host']['name']
        if noop == False:
        # remove sub from host
            results = put_json(api + "/hosts/" + str(unnecessary_consumers[i]['host']['id']) + "/remove_subscriptions", sub_hash)
            print str(results)
            # add the newly removed sub to the needing host
            results = put_json(api + "/hosts/" + str(unentitled[i]['host']['id']) + "/add_subscriptions", sub_hash)
            print results
        else:
            print "noop, won't perform any changes.."

        i = i+1
    
                
if __name__ == "__main__":
    main()
