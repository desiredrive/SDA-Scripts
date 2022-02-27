import cli
import re
import sys
import time
import datetime

print ("Vodoo Broadcast Checker 1.0!")

def convert_bytes(size):
    for x in ['bytes', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return "%3.1f %s" % (size, x)
        size /= 1024.0

    return size

def get_loopback0():
        loopback_output = cli.cli("show ip interface loopback 0")
        for line in loopback_output.splitlines():
                if 'Internet address' in line:
                        loopback_address=((re.compile( "(?<=address is).*(?=/)" ).search(line).group()))
        return (loopback_address)


def get_bcast_underlay():
        total_groups = []
        instance_table = []
        ser_ethernet_output = cli.cli("show run | se instance-id")
        for line in ser_ethernet_output.splitlines():
                if 'instance-id 8' in line:
                        instance_id=((re.compile( "(?<=instance-id ).*(?=)" ).search(line).group()))
                        instance_table.append(instance_id)
                if 'broadcast-underlay' in line:
                        multicast_group=((re.compile( "(?<=broadcast-underlay).*(?=)" ).search(line).group()))
                        total_groups.append(multicast_group)
        if all (v== total_groups[0] for v in total_groups):
                print ("All groups are the same!")
                return (total_groups,instance_table)
        else:
                cli.execute("send log Multicast Group for all Instances is: {}".format(total_groups))
                cli.execute("send log Different multicast groups across instances, script can't conintue")
                sys.exit()

def get_mroute_state(source, group):
        ip_mfib_output = cli.cli("show ip mfib {} {} | be Default".format(source, group))
        mcast_state = False
        for line in ip_mfib_output.splitlines():
                if ') Flags' in line:
                                mcast_state = True
                                cli.execute("send log Found this group: {}".format(line))
        return mcast_state

def flood_per_vlan(instance_list):
        flooding_table=[]
        for i in instance_list:
           lisp_output = cli.cli("show run | se instance-id {}".format(i))
           for line in lisp_output.splitlines():
                if 'broadcast-underlay' in line:
                      flooding_table.append(i)
        return flooding_table

def lisp_reconfiguration(flood_list, mcast_group):
       cmd_remove = ("conf t; router lisp; instance-id {}; service ethernet; no broadcast-underlay {}; end".format(flood_list[0], mcast_group))
       cmd_readd = ("conf t; router lisp; instance-id {}; service ethernet; broadcast-underlay {}; end".format(flood_list[0], mcast_group))
       cli.cli(cmd_remove)
       cli.execute("send log Removed Broadcast Underlay {} from Instance-id {}".format(mcast_group, flood_list[0]))
       cli.cli(cmd_readd)
       cli.execute("send log Configured Broadcast Underlay {} from Instance-id {}".format(mcast_group, flood_list[0]))

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

           cli.cli("set platform software trace fed {} punt debug".format(switch_type))
           cli.cli("set platform software trace fed {} inject debug".format(switch_type))
           cli.cli("no mon cap cap")
           cli.cli("mon cap cap con both match any buf si 100")
           cli.cli("mon cap cap start")
           time.sleep(30)
           current_datetime = datetime.datetime.utcnow()
           timestamp = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
           cli.cli("mon cap cap stop")
           cli.cli("mon cap cap export location flash:cpu.pcap")
           cli.cli("request pla sof trace archive last 1 days")                                 
           cli.cli("set pla sof trace fed {} all-modules notice".format(switch_type))
           cli.cli("show pla hard fed {switch_type} fwd-asic dump-all both asic 0 output flash:asic0_{date_time}.csv".format(switch_type=switch_type, date_time=timestamp))
           cli.cli("show pla hard fed {switch_type} fwd-asic dump-all both asic 1 output flash:asic1_{date_time}.csv".format(switch_type=switch_type, date_time=timestamp))
           cli.cli("show clock | append flash:automated_logs_{date_time}".format(datetime=timestamp))
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

                 cli.cli("set platform software trace fed {} punt debug".format(switch_type))
                 cli.cli("set platform software trace fed {} inject debug".format(switch_type))
                 cli.cli("no mon cap cap")
                 cli.cli("mon cap cap con both match any buf si 100")
                 cli.cli("mon cap cap start")
                 time.sleep(30)
                 current_datetime = datetime.datetime.utcnow()
                 timestamp = current_datetime.strftime('%Y-%m-%dT%H:%M:%SZ')
                 cli.cli("mon cap cap stop")
                 cli.cli("mon cap cap export location flash:cpu.pcap")
                 cli.cli("request pla sof trace archive last 1 days")                                 #Not Working?
                 cli.cli("set pla sof trace fed {} all-modules notice".format(switch_type))
                 cli.cli("show pla hard fed {switch_type} fwd-asic dump-all both asic 0 output flash:asic0_{date_time}.csv".format(switch_type=switch_type, date_time=timestamp))
                 # cli.cli("show pla hard fed {switch_type} fwd-asic dump-all both asic 1 output flash:asic1_{date_time}.csv".format(switch_type=switch_type, date_time=timestamp))
                 cli.cli("show clock | append flash:automated_logs_{date_time}".format(date_time=timestamp))
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

      loopback_ip = get_loopback0()
      cli.execute("send log Loopback 0 IP is: {}".format(loopback_ip))

      mcast_group, instance_list = get_bcast_underlay()
      cli.execute("send log Multicast Group for all Instances is: {}".format(mcast_group[0]))

      mcast_state = get_mroute_state(loopback_ip, mcast_group[0])
      if mcast_state == True:
             cli.execute("send log The S,G is installed, no need to reconfigure LISP")
             clean_iosp()
      if mcast_state == False:
             cli.execute("send log S,G is Lost")
             cli.execute("send log "+ (cli.cli("show clock")))
             #logging_stuff()
             cli.execute("send log Reconfiguring LISP broadcast-underlay")
             flood_list = flood_per_vlan(instance_list)
             lisp_reconfiguration(flood_list, mcast_group[0])
             clean_iosp()


