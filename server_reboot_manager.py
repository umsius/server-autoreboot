#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
from pathlib import Path

class ServerRebootManager:
    def __init__(self):
        self.config_dir = "/opt/server-autoreboot/configs"
        self.servers = []
        self.load_servers()
    
    def load_servers(self):
        """Load all server configurations"""
        config_files = Path(self.config_dir).glob("*.env")
        for config_file in config_files:
            server_name = config_file.stem
            self.servers.append({
                'name': server_name,
                'config': str(config_file),
                'id': server_name.replace('server', '')
            })
    
    def reboot_single_server(self, server_id):
        """Reboot a single server"""
        server = next((s for s in self.servers if s['id'] == str(server_id)), None)
        if server:
            cmd = f"sudo /opt/server-autoreboot/reboot_service.py {server['config']}"
            subprocess.run(cmd, shell=True)
        else:
            print(f"Server {server_id} not found")
    
    def reboot_all_servers(self):
        """Reboot all servers"""
        for server in self.servers:
            print(f"Rebooting {server['name']}...")
            self.reboot_single_server(server['id'])
    
    def check_status(self):
        """Check status of all servers"""
        for server in self.servers:
            print(f"\n=== {server['name']} ===")
            # Check if server is reachable
            result = subprocess.run(['ping', '-c', '1', '-W', '1', server.get('ip', 'localhost')], 
                                  capture_output=True)
            if result.returncode == 0:
                print("✅ Server is online")
            else:
                print("❌ Server is offline")

def main():
    parser = argparse.ArgumentParser(description='Manage server reboots')
    parser.add_argument('action', choices=['reboot', 'status', 'reboot-all'])
    parser.add_argument('--server', type=str, help='Server ID (1,2,3,4)')
    
    args = parser.parse_args()
    manager = ServerRebootManager()
    
    if args.action == 'reboot':
        if not args.server:
            print("Please specify --server")
            sys.exit(1)
        manager.reboot_single_server(args.server)
    elif args.action == 'reboot-all':
        manager.reboot_all_servers()
    elif args.action == 'status':
        manager.check_status()

if __name__ == '__main__':
    main()