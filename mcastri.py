w__copyright__ = "Copyright (c) 2018-2023 Cisco Systems. All rights reserved."

from dataclasses import dataclass
import radkit_client
import ipaddress
import re
import sys
import json
import datetime
from datetime import datetime

from radkit_client.sync import (
    # For the creation of the context.
    create_context,
    # Cloud-based login methods.
    certificate_login,
    access_token_login,
    sso_login,
    # Direct login method.
    direct_login,

)


def _run_code():
    # Ask for user input.
    #email = input("email> ")
    email = "@cisco.com"
    #domain = input("domain> ")
    domain = "PROD"
    #service_serial = input("service serial> ")
    service_serial=""

    # Connect to the given service, using SSO login.
    client = certificate_login(identity=email, domain=domain)
    global service
    service = client.service(service_serial).wait()

def device_builder(mgmt_ip):
    device_construct = {
        "loopback0":"",
        "hostname": "",
        "device_model":"",
        "device_version":"",
        "radkit_mgmt_ip":""
    }

    try:
        device_inventory = service.inventory.filter('host', '^{}$'.format(mgmt_ip))
        device_name = list(device_inventory.keys())
        try:
            device_inventory = service.inventory[device_name[0]]
            device_construct['radkit_mgmt_ip']= service.inventory[device_name[0]].host
        except (IndexError, ValueError):
            print ("Device {} not in RADKIT inventory".format(mgmt_ip))
            return
        cmd1 = 'show ip interface loopback0 | i Internet|line'
        cmd2 = 'show version | i ptime'
        cmd8 = 'show ver | i IOS Soft|bytes of memory'
        commands = device_inventory.exec([cmd1,cmd2,cmd8]).wait()
        try:
         lo0 = commands.result["{}".format(cmd1)].data
        except:
         return
        device_construct['hostname'] = device_name[0]
        model_ios = commands.result ["{}".format(cmd8)].data


    except ValueError:
        print ("RADKIT Could not retrieve information about the device")
    
    for line in lo0.splitlines():
            #if "line protocol is up" in line: 
            #   print ("Loopback0 is UP")
            if "line protocol is down" in line: 
                print("Loopback0 is down at device: {}".format(mgmt_ip))
            if "Invalid input" in line:
                print("Loopback 0 does not exist in {} verify the configuration".format(mgmt_ip))
            if "Internet address" in line:
                loopback_address=re.compile( "(?<=address is).*(?=/)" ).search(line).group().strip()
                device_construct["loopback0"]=loopback_address

    for line in model_ios.splitlines():
         if "Cisco IOS" in line:
            IOSversion = re.compile( "(?<=Version).*(?=\[)|(?<=Version)(.*)(?=, REL)" ).search(line).group().strip()
            device_construct["device_version"]=IOSversion
         if "processor" in line:
            model = re.compile( "(?<=cisco ).*(?=.\(.*proces)" ).search(line).group().strip()
            device_construct["device_model"]=model

    return device_construct

def get_local_mroutes(mgmt_ip,vrf,model):

    if "9KV" or "93" in model:
        mode = "switch active"
    if "94" in model:
        mode = "active"
    print (model)

    print ("Getting local mroutes from {}".format(mgmt_ip))

    mroutecmd = "show ip mroute vrf {} 224.0.1.129".format(vrf)
    mrouteoutput = get_any_single_output(mgmt_ip,mroutecmd)

    mroutes={}
    n=0
    print ("Processing mroutes...")
    for line in mrouteoutput.splitlines():
        mrouteconstruct = {
        "source":"",
        "group":"",
        "iif":"",
        "localvlan":False,
        "oillisp":False,
        "riindexes":"",
        "ridecoded":""
        }
        if "flags: " and "224.0.1.129)"in line:
                sg = re.compile("(?<=\().*(?=\),)").search(line).group().strip()
                sg = sg.split(",")
                mrouteconstruct['source']=sg[0].strip()
                mrouteconstruct['group']=sg[1].strip()
                mroutes[n]=mrouteconstruct
                n+=1

        if "Incoming" in line:
                a = n-1
                iif = re.compile("(?<=: ).*(?=,)").search(line).group().strip()
                if iif=="Vlan1040":
                    mroutes[a]['localvlan']=True
                if iif=="Vlan1043":
                    mroutes[a]['localvlan']=True
                mroutes[a]['iif']=iif



    killarray=[]
    for line in mroutes:
        if "LISP" in (mroutes[line]['iif']):
                killarray.append(line)
    for line in killarray:
        del mroutes[line]

    killarray=[]
    for line in mroutes:
        if (mroutes[line]['localvlan']==False):
                killarray.append(line)
    for line in killarray:
        del mroutes[line]

    for line in mroutes:
        a = line
        group = mroutes[line]['group']
        source = mroutes[line]['source']
        print ("Processing elegible mroute {},{} ...".format(source,group))
        mfibcmd=("show platform software fed {} ip mfib vrf {} {} {}".format(mode,vrf,group,source))
        #print (mfibcmd)
        mfibop=get_any_single_output(mgmt_ip,mfibcmd)
        for line in mfibop.splitlines():
           if "LISP" in line:
               mroutes[a]['oillisp']=True
    killarray=[]
    for line in mroutes:
        if  (mroutes[line]['oillisp'])==False:
                killarray.append(line)
    for line in killarray:
        del mroutes[line]

    
    for line in mroutes:
        a = line
        group = mroutes[line]['group']
        source = mroutes[line]['source']
        print ("Verifying RIs for {} {}".format(source,group))
        mfibcmd=("show platform software fed {} ip mfib vrf {} {} {} detail".format(mode,vrf,group,source))
        mfibop=get_any_single_output(mgmt_ip,mfibcmd)
        rindexes=[]
        for line in mfibop.splitlines():
            if ("ri_list" in line) or ("uri" in line) or ("ri[" in line):
              if "ri[" in line:
                  if "/" not in line:
                    try:
                            ri = re.compile("0[xX][0-9a-fA-F]+").search(line).group().strip()
                            ri = int(ri,16)
                            ri = str(ri)
                            rindexes.append(ri)

                    except (AttributeError):
                            pass
              if "uri" in line:
                     uris = line.split("ref")
                     for i in uris:
                            if "uri" in i:
                                   uri = re.compile("(?<=uri[0-9]:).*(?= ri)").search(i).group().strip()
                                   rindexes.append(uri)
        if len(rindexes) == 0:
            print ("Potential problem, 0 indexes for S,G, dumping detail output")
            print (mfibop)
        
        rindexes =list(set(rindexes))
        rwips=[]
        print ("Decoding RIs for {} {}".format(source,group))
        for line in rindexes:
            if "49151" in line:
                print ("RI 49151 detected, underlay S,G might not exist, ignoring...")
                rwip ="99999"
                rwips.append(rwip)
                continue
            rwrcmd=("show platform hard fed {} fwd resource asic 0 rewrite range {} {} | i IP:".format(mode,line,line))
            rwrop=get_any_single_output(mgmt_ip,rwrcmd)
            for line in rwrop.splitlines():
                if "#" not in line:
                    try:
                        rwip = re.compile("(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})").search(line).group().strip()
                        if ("232" in rwip) or ("239.0." in rwip):
                            rwips.append(rwip)
                    except (AttributeError):
                        print ("Unexpected RI decode for RI {}".format(line))
                        print (line)
                        rwip = "0"
                        rwips.append(rwip)

        mroutes[a]['riindexes']=rindexes
        mroutes[a]['ridecoded']=rwips
    
    return (mroutes)

def rewrite_validation(mroutes):
    flood = False
    for line in mroutes:
        if (len(mroutes[line]['ridecoded']))==0:
            print (line)
            print ("The above S,G has its RI corrupted but both RIs are zeroed, can be false negative, please ignore.")
            continue
        for i in (mroutes[line]['ridecoded']):
            if "239.0." in i:
                flood = True
            if "99999" in i:
                flood = True
        if flood == False:
            print (line)
            print ("The above S,G has its RI corrupted!")

    return (flood)


def get_any_single_output(mgmt_ip,command: str):
    try:
        device_inventory = service.inventory.filter('host', '^{}$'.format(mgmt_ip))
        device_name = list(device_inventory.keys())        
        device_inventory = service.inventory[device_name[0]]
        commands = device_inventory.exec([command]).wait()
        output = commands.result["{}".format(command)].data
    except ValueError:
        print ("Device not found in Radkit Inventory")
    
    return output

def all_devices_builder():
    print ("Profiling inventory devices as fabric devices, this can take up some minutes...")
    devices_list = {}
    n = 0
    for line in service.inventory:
        host = service.inventory[line].host
        if ("xxx" in host):
        #if ("xx" in host) or ("xxx" in host) or ("xxx" in host):
            print ("Profiling device {} ...".format(host))
            device_info = device_builder(host)
            devices_list[n]=device_info
            n+=1

    return (devices_list)


def initial_setup():
    with open ("log.txt","a") as fp:
            timez = datetime.now()
            msg = ("Start time: {}".format(timez))
            fp.write(msg)
            fp.write('\n')
    devices_list = all_devices_builder()
    vrf = "ACCESS_VN"
    for line in devices_list:        
        with open ("log.txt","a") as fp:
            fp.write('\n')
            timez = datetime.now()
            msg = ("Calculating mroutes: {}".format(timez))
            fp.write(msg)
            fp.write('\n')
        current_device = devices_list[line]['radkit_mgmt_ip']
        current_model = devices_list[line]['device_model']
        mroutes = get_local_mroutes(current_device,vrf,current_model)
        if len(mroutes)==0:
            print ("No local S,Gs with LISP OIL found in {}".format(current_device))
        else:
            pass
            #print ("Edge {} Mroute Sumamry:".format(current_device))
            #print (mroutes)
        rewrite_validation(mroutes)
        #print ("S,G Summary for device {} :".format(current_device))
        #print (mroutes)
        with open ("log.txt","a") as fp:
            fp.write('\n')
            msg = ("S,G Summary for device {} :\n".format(current_device))
            fp.write(msg)
            fp.write('\n')
            fp.write('\'')
            json.dump(mroutes,fp)
            fp.write('\'')
            fp.write('\n')
        print ("mroutes for {} saved in log.txt".format(current_device))

def main():
    with create_context():
        _run_code()
        initial_setup()


if __name__ == "__main__":
    main()
