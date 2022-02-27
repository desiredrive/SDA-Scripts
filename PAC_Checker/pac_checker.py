'''
' Created By Alejandro Jon jalejand@cisco.com Version 1.2b
  Run it with Python3
'''
import os
import cli
import re
import sys
import time
import datetime


print ("PAC Checker 1.2b")

def get_radius_servers():
        radius_server_list = []
        radius_servers_op = cli.cli("show run | se radius server")
        for line in radius_servers_op.splitlines():
                if 'radius server' in line:
                        server_name=((re.compile( "(?<=radius server ).*()" ).search(line).group()))
                        radius_server_list.append(server_name)
        return radius_server_list


def get_radius_config(target_radius):
    radius_config = cli.cli("show run | se radius server {}".format(target_radius))
    for line in radius_config.splitlines():
        if 'key' in line:
            if 'pac' in line:
                cli.execute("send log PAC Key found in radius server {}".format(target_radius))
                get_previous_config()
                readd_cli = line.replace('pac ','')
                remove_cli = "no"+(line)
                change_flag = change_config(readd_cli, remove_cli, target_radius)
                return change_flag
            else:
                print ("Shared Secret does not include any PAC")
                change_flag = False
                return change_flag

def change_config(readd_cli, remove_cli, target_radius):
    cmd_remove = ("conf t; radius server {}; {}; {}; end".format(target_radius, remove_cli, readd_cli))
    cli.cli(cmd_remove)
    cli.execute("send log removed and re-added PAC Key from {}".format(target_radius))
    change_stat = True
    return change_stat

def get_previous_config():
        cli.cli("show run | redirect show_run_previous.log")

def get_new_config():
        cli.cli("show run | redirect show_run_new.log")
        cli.execute("send log Created show_run_previous.log and show_run_new.log in flash, please attach them to the case")

def get_accounting_list(priv_accounting):
    current_accounting = cli.cli("show run | i identity default start-stop")
    for line in current_accounting.splitlines():
            if priv_accounting in line:
                print ("Accounting List Contains Private Servers")
                change_flag = False
                return change_flag
            else:
                print ("Accounting List Contains DNASpaces Servers")
                cli.execute("send log Wrong accounting list, will change to the original one".format())
                change_flag = change_accounting_list(priv_accounting)
                return change_flag

def change_accounting_list(priv_accounting):
    cmd_accounting = ("conf t; aaa accounting identity default start-stop group {}; end".format(priv_accounting))
    cli.cli(cmd_accounting)
    cli.execute("send log Accounting list changed to {}".format(priv_accounting))
    change_stat = True
    return change_stat

def clean_iosp():
        try:
            os.remove("/data/iosp.log")
            print("IOSP log is succesfully removed")
        except OSError as error:
            print(error)

if __name__ == "__main__":

	first_radius_server = "10.88.244.144"
	second_radius_server = "10.88.244.144"
        target_radius_name = [first_radius_server, second_radius_server]
        radius_servers = get_radius_servers()
        for line in radius_servers:
                if target_radius_name[0] in line:
                        target_radius = line
                        print ("Target Radius Server Found, checking shared secret CLI")
                        change_flag_a = get_radius_config(target_radius_name[0])
                if target_radius_name[1] in line:
                        target_radius = line
                        print ("Target Radius Server Found, checking shared secret CLI")
                        change_flag_b = get_radius_config(target_radius_name[1])

        target_account_list = "original_accounting_name"
        change_flag_c = get_accounting_list(target_account_list)

        print (change_flag_a, change_flag_b, change_flag_c)

        if (change_flag_a==True or change_flag_b==True or change_flag_c==True):
                print ("Changes Detected!")
                get_new_config()

        clean_iosp()
