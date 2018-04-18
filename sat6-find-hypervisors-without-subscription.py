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
from satellite_api import get_json, post_json, put_json, print_json

try:
    import requests
except ImportError:
    print "Please install the python-requests module."
    sys.exit(-1)
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

parser = argparse.ArgumentParser(description='sat6-add-to-host-collection.py')
parser.add_argument('-v', '--verbose' , action="store_true", dest='verbose',  help='Be verbose')
args =parser.parse_args()

api = "api/"
katello_api = "katello/api/"
post_headers = {'content-type': 'application/json'}
ssl_verify = False

org_name = "<someorg>"
hostname = socket.gethostname()
username = "<someusername>"
password = "<somepassword>"

# Take from these
unnecessary_consumers = []
# And give to these
unentitled = []

def main():
    """
    Main method that gets organizations, hosts and host collections
    and them adds the host to the host collections specified 
    """

    orgs = get_json(username, password, katello_api + "organizations/")
    for org in orgs["results"]:
        if org['name'] == org_name:
           org_id = org['id']
           print "Organization " + org_name + " has ID " + str(org['id']) + "\n"

    try:
        org_id
    except NameError:
        print "Organization " + org_name + " does not exist. Exiting..." 
        exit(1)

    hypervisors = get_json(username, password, api + "organizations/" + str(org_id) + "/hosts?search=name+~+virt-who&per_page=1000")
    count = 0
    for hypervisor in hypervisors["results"]:
        guests = []
        hyper_hash = {}
        details = get_json(username, password, api + "hosts/" + str(hypervisor["id"]))
        if details["subscription_facet_attributes"]["virtual_guests"]:
            has_guests = True
        else:
            has_guests = False
        
        hypervisor_subscription_json = get_json(username, password, api + "hosts/" + str(hypervisor["id"]) + "/subscriptions")
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
        # remove sub from host
        results = put_json(username, password, api + "/hosts/" + str(unnecessary_consumers[i]['host']['id']) + "/remove_subscriptions", sub_hash)
        print str(results)
        # add the newly removed sub to the needing host
        results = put_json(username, password, api + "/hosts/" + str(unentitled[i]['host']['id']) + "/add_subscriptions", sub_hash)
        print results
        
        i = i+1
    
                
if __name__ == "__main__":
    main()
