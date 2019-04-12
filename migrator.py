#!/usr/bin/env python3

import argparse
import json
import os
import paramiko
import socket
import subprocess
import sys

def make_arg_parser():
    p = argparse.ArgumentParser()
    p.add_argument("--to-server", help="Server to migrate from")
    p.add_argument("--username", help="Username")
    p.add_argument("--password", help="Password")
    p.add_argument("--pid", help="Process to migrate")
    return p

def fix_ip_in_img(image_file, ip_address):
    decode_proc = subprocess.Popen(["crit", "decode", "-i", image_file, "-o", "/tmp/tmp.json"])
    decode_proc.wait()
    os.remove(image_file)
    with open("/tmp/tmp.json", "r") as in_file, open("/tmp/tmp2.json", "w+") as out_file :
        data = json.load(in_file)
        print(data)

        to_change = [entry["isk"] for entry in data["entries"] if entry["type"] == "INETSK"]
        for entry in to_change:
            entry["src_addr"] = [ip_address]
        s = json.dumps(data, indent=4, sort_keys=True)
        print(s)
        out_file.write(s)
    
    encode_proc = subprocess.Popen(["sudo", "crit", "encode", 
        "-i", "/tmp/tmp2.json", "-o", image_file])
    encode_proc.wait()

def main():
    args = make_arg_parser().parse_args(sys.argv[1:])
 
    # On localhost
    dump_proc = subprocess.Popen(["sudo", "criu", "dump", "-t", args.pid, 
        "--tcp-established", "-v4", "-D", "/tmp/criu/criu_transfer", "-o", "dump.log"])
    dump_proc.wait()
    
    fix_ip_in_img("/tmp/criu/criu_transfer/files.img", "0.0.0.0")

    # Fix up the source address
    replace_in_image("/tmp/criu/criu_transfer/files.img", args.to_server)


    tar_proc = subprocess.Popen(["sudo", "tar", "czvf", 
                                "/tmp/criu/criu_transfer.tar.gz", "/tmp/criu/criu_transfer"])
    tar_proc.wait()
    copy_proc = subprocess.Popen(["sudo", "scp", "/tmp/criu/criu_transfer.tar.gz", 
        args.username + "@" + args.to_server + ":/tmp"])
    copy_proc.wait()

    # On other host
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(args.to_server, username=args.username, password=args.password)
    ssh.exec_command("cd /tmp/criu")
    ssh.exec_command("tar xvf criu_transfer.tar.gz")
    stdin, stdout, stderr = ssh.exec_command("sudo -S -p '' criu restore " \
        "--tcp-established --restore-detached -D /tmp/criu/criu_transfer -d -v4 -o restore.log", get_pty=True)
    stdin.write(args.password + "\n")
    stdin.flush()
    print(stdout.readlines())
    print(stderr.readlines())
    ssh.close()

if __name__ == "__main__":
    main()

