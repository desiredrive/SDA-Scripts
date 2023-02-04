'''
' Created By Alejandro Jon jalejand@cisco.com Version 1.0b
  Run it with Python3
'''

import cli
import re
import sys
import os
import time
import datetime

print ("Acces-Tunnel Watchdog 1.0b")

def convert_bytes(size):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0

    return size

def get_model():
  model_number = cli.cli("show version | include Model Number")
  model_number = model_number.partition(":")[2]
  #IF Catalyst 9300 
  if "C9300" in model_number:
    switch_type = "switch active"
  #IF Catalyst 9400
  elif "C9400" in model_number:
    switch_type = "active"
  return switch_type

def get_loopback0():
        loopback_output = cli.cli("show ip interface loopback 0")
        for line in loopback_output.splitlines():
                if 'Internet address' in line:
                        loopback_address=((re.compile( "(?<=address is).*(?=/)" ).search(line).group()))
        return (loopback_address)

def get_access_tunnels(loopback, sw_mode):
        ios_at_dict_list = []
        fed_at_dict_list = []
        total_acs = 0
        sats_output = cli.cli("show access-tunnel summary")
        for line in sats_output.splitlines():
                if '4789' in line:
                  total_acs = total_acs + 1
                  re1 =((re.compile( "(?<=  ).*(?=  0  )" ).search(line).group()))
                  re1 = re1.replace(loopback, '')
                  re1 = re1.strip()
                  re2 =((re.compile( "(?<=Ac)[0-9]+" ).search(line).group()))
                  re2 = "Ac"+re2
                  acdict = {}
                  acdict['AC_ID'] = re2
                  acdict['Dest_IP'] = re1
                  ios_at_dict_list.append(acdict.copy())
        fedats_output = cli.cli("show platform software fed {} ifm interface access-tunnel".format(sw_mode))
        for line in fedats_output.splitlines():
                  if 'READY' in line:
                    re1 =((re.compile( "0[xX][0-9a-fA-F]+" ).search(line).group()))
                    re2 =((re.compile( "(?<=Ac)[0-9]+" ).search(line).group()))
                    re2 = "Ac"+re2
                    feddict = {}
                    feddict['AC_ID'] = re2
                    feddict['IF_ID'] = re1
                    fed_at_dict_list.append(feddict.copy())
        return (ios_at_dict_list, fed_at_dict_list)

def v4mismatch(lists):
      if len(lists[0]) == len(lists[1]):
          log3 = ("Access-Tunnel count between IOS and FED are the same, not hitting CSCwc70997")
          print (log3)
      else:
          log4 = ("Access-Tunnel mismatch between IOS and FED, compare AC count hitting CSCwc70997")
          cli.execute("send log Access-Tunnel mismatch between IOS and FED, compare AC count")

def ri_handle_chec(list_dict, sw_mode):
    for i in list_dict[1]:
        ac_value = i['AC_ID']
        ifid_value = i['IF_ID']

        get_L2RI = cli.cli("show platform software fed {} ifm if-id {} | i L2 Br".format(sw_mode,ifid_value))
        RI_hdl = ((re.compile( "0[xX][0-9a-fA-F]+" ).search(get_L2RI).group()))
        get_RI_abs = cli.cli("show platform hardware fed {} fwd abs print {} 1 | i IP:".format(sw_mode,RI_hdl))
        
        rilist = []
        for i in get_RI_abs.splitlines():
            if 'Dst IP' in i :
                dst_ri = ((re.compile( "(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})" ).search(i).group()))
                rilist.append(dst_ri)
        state = chkList(rilist, ac_value)
        if state == True:
            for i in list_dict[0]:
                if i['AC_ID'] == ac_value :
                    ap_ip = i['Dest_IP']
                    if (dst_ri) != (ap_ip):
                        log1 = ("The AP with {} as tunnel has {} programmed in FED, and {} in IOS, misprogramming detected".format(ac_value, dst_ri, ap_ip))
                        print (log1)
                        apname = get_AP_name(ap_ip)
                        log2 = ("A programming mismatch has been detected for AP: {} , reset the CAPWAP tunnel from the controller".format(apname))
                        cli.execute("send log "+log1)
                        cli.execute("send log "+log2)
                    elif (dst_ri) == (ap_ip):           
                        print ("The AP with {} as tunnel has {} programmed in FED, and {} in IOS, NO misprogramming detected".format(ac_value, dst_ri, ap_ip))
                        #apname = get_AP_name(ap_ip) 
                        #print ("A programming mismatch has been detected for AP: {} , reset the CAPWAP tunnel from the controller".format(apname))

def get_AP_name(ap_ip):
    ipdt = cli.cli("show device-tracking database address {} | be Network".format(ap_ip))
    intname = ((re.compile( " (?:[A-Z][A-Za-z_-]*[a-z]|[A-Z])\s?\d+(?:\/\d+)*(?::\d+)?(?:\.\d+)?" ).search(ipdt).group()))
    cdp = cli.cli("show cdp neighbor {} de | i Device".format(intname)).replace('Device ID: ', '').strip()

    return (cdp)

def chkList(lst, acv):
    if len(lst) < 0:
        res = True
    res = lst.count(lst[0]) == len(lst)
 
    if(res):
        print("All RIs for {} AP are the same".format(acv))
        return True
    else:
        print("Not all RIs are the same for {} AP, please contact Cisco TAC ".format(acv))
 
def logging_stuff():
       mem_re = re.compile(r"""\((\d+).*\)""")
       # CHECK AVAILABLE MEM
       flash_mem = cli.cli("dir flash: | include bytes free")
       available_memory = mem_re.findall(flash_mem)[0]
       free_space = convert_bytes(int(available_memory))
       #IF LESS THAN 2 GB AVAILABLE THEN BREAK, ELSE CONTINUE
       if "TB" in free_space:
           model_number = cli.cli("show version | include Model Number")
           model_number = model_number.partition(":")[2]
           #IF Catalyst 9300 
           if "C9300" in model_number:
               switch_type = "switch active"
           #IF Catalyst 9400
           elif "C9400" in model_number:
               switch_type = "active"

           current_datetime = datetime.datetime.utcnow()
           timestamp = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
           cli.cli("show logg | append flash:automated_logs_{date_time}".format(datetime=timestamp))
           cli.execute("send log Logs collected")
       elif "GB" in free_space:
           free_space = free_space.replace("GB", "")
           #IF LESS THAN 2 GB AVAILABLE THEN BREAK, ELSE CONTINUE
           if float(free_space.strip()) >= 2:
                 model_number = cli.cli("show version | include Model Number")
                 model_number = model_number.partition(":")[2]
                 #IF Catalyst 9300 
                 if "C9300" in model_number:
                     switch_type = "switch active"
                     switch_type
                 #IF Catalyst 9400
                 elif "C9400" in model_number:
                     switch_type = "active"

                 current_datetime = datetime.datetime.utcnow()
                 timestamp = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
                 cli.cli("show logg | append flash:automated_logs_{date_time}".format(date_time=timestamp))
                 cli.execute("send log Logs collected")
           else:
                 print("Not enough memory to write logs to flash!")

       else:
          print("IN ELSE")
          print("Not enough memory to write logs to flash!")
           
def clean_iosp():
        try:
            os.remove("/data/iosp.log")
            print("IOSP log is succesfully removed")
        except OSError as error:
            print(error)

if __name__ == "__main__":

    sw_mode = get_model()
    loopback = get_loopback0()
    list_dict = get_access_tunnels(loopback,sw_mode)
    v4mismatch(list_dict)

    #Checking RI handlers
 
    ri_check = ri_handle_chec(list_dict, sw_mode)


    clean_iosp()
