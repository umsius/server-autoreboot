#!/usr/bin/env python3
"""
Docker Container Health Check Script
Supports multiple servers and detailed container status reporting
"""

import subprocess
import sys
import json
import argparse
from datetime import datetime
from typing import Dict, List, Tuple, Optional

class DockerChecker:
    def __init__(self, verbose: bool = False, server_id: Optional[str] = None):
        self.verbose = verbose
        self.server_id = server_id
        self.server_name = self.get_server_name()
        
    def get_server_name(self) -> str:
        """Get server name or ID"""
        if self.server_id:
            return f"Server-{self.server_id}"
        
        try:
            # Try to get hostname
            result = subprocess.run(['hostname'], capture_output=True, text=True)
            return result.stdout.strip()
        except:
            return "Unknown-Server"
    
    def run_docker_command(self, command: List[str]) -> Tuple[int, str, str]:
        """Run docker command and return output"""
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=30
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return 124, "", "Command timeout"
        except FileNotFoundError:
            return 127, "", "Docker not found"
        except Exception as e:
            return 1, "", str(e)
    
    def get_all_containers(self) -> List[Dict]:
        """Get all containers (running and stopped)"""
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'ps', '-a', '--format', 'json'
        ])
        
        if returncode != 0 or not stdout:
            return []
        
        containers = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    container = json.loads(line)
                    containers.append(container)
                except json.JSONDecodeError:
                    continue
        
        return containers
    
    def get_running_containers(self) -> List[Dict]:
        """Get only running containers"""
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'ps', '--format', 'json'
        ])
        
        if returncode != 0 or not stdout:
            return []
        
        containers = []
        for line in stdout.strip().split('\n'):
            if line:
                try:
                    container = json.loads(line)
                    containers.append(container)
                except json.JSONDecodeError:
                    continue
        
        return containers
    
    def check_container_health(self, container_name: str) -> Dict:
        """Check health status of a specific container"""
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'inspect', '--format', '{{json .State.Health}}', container_name
        ])
        
        if returncode == 0 and stdout and stdout != 'null':
            try:
                health = json.loads(stdout)
                return {
                    'status': health.get('Status', 'unknown'),
                    'log': health.get('Log', [])[-1] if health.get('Log') else None
                }
            except:
                return {'status': 'unknown', 'log': None}
        
        # Check if container is running
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'inspect', '--format', '{{.State.Status}}', container_name
        ])
        
        if returncode == 0:
            return {'status': stdout.strip(), 'log': None}
        
        return {'status': 'unknown', 'log': None}
    
    def check_docker_service(self) -> bool:
        """Check if Docker service is running"""
        returncode, stdout, stderr = self.run_docker_command(['docker', 'info'])
        return returncode == 0
    
    def get_container_stats(self, container_name: str) -> Dict:
        """Get container resource usage stats"""
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'stats', '--no-stream', '--format', 'json', container_name
        ])
        
        if returncode == 0 and stdout:
            try:
                return json.loads(stdout)
            except:
                pass
        
        return {}
    
    def print_container_table(self, containers: List[Dict], show_all: bool = False):
        """Print containers in a formatted table"""
        if not containers:
            print("📦 No containers found")
            return
        
        # Define headers
        headers = ["CONTAINER", "STATUS", "HEALTH", "IMAGE", "UPTIME"]
        if show_all:
            headers.append("STATS")
        
        # Calculate column widths
        col_widths = [len(h) for h in headers]
        for container in containers:
            name = container.get('Names', container.get('Name', 'unknown'))[:30]
            status = container.get('State', 'unknown')[:20]
            health = "N/A"
            image = container.get('Image', 'unknown')[:30]
            uptime = container.get('Status', 'unknown')[:20]
            
            if 'health' in container:
                health = container.get('health', {}).get('status', 'N/A')[:10]
            
            col_widths[0] = max(col_widths[0], len(name))
            col_widths[1] = max(col_widths[1], len(status))
            col_widths[2] = max(col_widths[2], len(health))
            col_widths[3] = max(col_widths[3], len(image))
            col_widths[4] = max(col_widths[4], len(uptime))
        
        # Print header
        print("\n" + "=" * (sum(col_widths) + len(headers) * 3))
        header_line = " | ".join([h.ljust(col_widths[i]) for i, h in enumerate(headers)])
        print(f"📊 DOCKER CONTAINERS STATUS - {self.server_name}")
        print(header_line)
        print("-" * (sum(col_widths) + len(headers) * 3))
        
        # Print rows
        for container in containers:
            name = container.get('Names', container.get('Name', 'unknown'))[:30]
            status = container.get('State', 'unknown')[:20]
            
            # Health status
            health = "N/A"
            health_symbol = "⚪"
            if 'health' in container:
                health_status = container.get('health', {}).get('status', 'unknown')
                health = health_status[:10]
                if health_status == 'healthy':
                    health_symbol = "✅"
                elif health_status == 'unhealthy':
                    health_symbol = "❌"
                elif health_status == 'starting':
                    health_symbol = "🟡"
                else:
                    health_symbol = "⚠️"
            else:
                if status == 'running':
                    health_symbol = "🟢"
                elif status == 'exited':
                    health_symbol = "🔴"
                elif status == 'restarting':
                    health_symbol = "🟡"
            
            image = container.get('Image', 'unknown')[:30]
            uptime = container.get('Status', 'unknown')[:20]
            
            row = [
                f"{health_symbol} {name}".ljust(col_widths[0]),
                status.ljust(col_widths[1]),
                health.ljust(col_widths[2]),
                image.ljust(col_widths[3]),
                uptime.ljust(col_widths[4])
            ]
            
            print(" | ".join(row))
        
        print("=" * (sum(col_widths) + len(headers) * 3))
    
    def check_health_summary(self) -> Dict:
        """Get health summary of all containers"""
        containers = self.get_all_containers()
        
        summary = {
            'total': len(containers),
            'running': 0,
            'exited': 0,
            'paused': 0,
            'healthy': 0,
            'unhealthy': 0,
            'unknown': 0,
            'problematic': []
        }
        
        for container in containers:
            status = container.get('State', 'unknown')
            
            if status == 'running':
                summary['running'] += 1
                
                # Check health for running containers
                health_info = self.check_container_health(container.get('Names', container.get('Name', '')))
                health_status = health_info.get('status', 'unknown')
                
                if health_status == 'healthy':
                    summary['healthy'] += 1
                elif health_status == 'unhealthy':
                    summary['unhealthy'] += 1
                    summary['problematic'].append({
                        'name': container.get('Names', container.get('Name', 'unknown')),
                        'status': status,
                        'health': health_status,
                        'issue': 'Container is unhealthy'
                    })
            elif status == 'exited':
                summary['exited'] += 1
                summary['problematic'].append({
                    'name': container.get('Names', container.get('Name', 'unknown')),
                    'status': status,
                    'health': 'N/A',
                    'issue': 'Container has exited'
                })
            elif status == 'paused':
                summary['paused'] += 1
                summary['problematic'].append({
                    'name': container.get('Names', container.get('Name', 'unknown')),
                    'status': status,
                    'health': 'N/A',
                    'issue': 'Container is paused'
                })
            else:
                summary['unknown'] += 1
        
        return summary
    
    def print_summary(self):
        """Print health summary"""
        if not self.check_docker_service():
            print("❌ Docker service is NOT running!")
            return False
        
        summary = self.check_health_summary()
        
        print(f"\n📊 DOCKER HEALTH SUMMARY - {self.server_name}")
        print(f"📍 Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("-" * 50)
        print(f"📦 Total containers: {summary['total']}")
        print(f"🟢 Running: {summary['running']}")
        print(f"🔴 Exited: {summary['exited']}")
        print(f"⏸️  Paused: {summary['paused']}")
        print(f"❓ Unknown: {summary['unknown']}")
        print(f"✅ Healthy: {summary['healthy']}")
        print(f"⚠️  Unhealthy: {summary['unhealthy']}")
        
        if summary['problematic']:
            print(f"\n⚠️ PROBLEMATIC CONTAINERS ({len(summary['problematic'])}):")
            for prob in summary['problematic']:
                print(f"  • {prob['name']}: {prob['issue']}")
            return False
        else:
            print("\n✅ All containers are healthy!")
            return True
    
    def check_specific_container(self, container_name: str):
        """Check specific container in detail"""
        print(f"\n🔍 DETAILED CHECK FOR CONTAINER: {container_name}")
        print("-" * 50)
        
        # Get container info
        returncode, stdout, stderr = self.run_docker_command([
            'docker', 'inspect', container_name
        ])
        
        if returncode == 0 and stdout:
            try:
                info = json.loads(stdout)[0]
                state = info.get('State', {})
                
                print(f"📦 Name: {info.get('Name', 'unknown')}")
                print(f"🆔 ID: {info.get('Id', 'unknown')[:12]}")
                print(f"🖼️  Image: {info.get('Config', {}).get('Image', 'unknown')}")
                print(f"⚙️  Status: {state.get('Status', 'unknown')}")
                print(f"🔄 Restart Count: {state.get('RestartCount', 0)}")
                
                if state.get('StartedAt'):
                    print(f"▶️  Started: {state.get('StartedAt')}")
                if state.get('FinishedAt') and state.get('FinishedAt') != '0001-01-01T00:00:00Z':
                    print(f"⏹️  Finished: {state.get('FinishedAt')}")
                
                # Health check
                health = info.get('State', {}).get('Health', {})
                if health:
                    print(f"\n💊 Health Status: {health.get('Status', 'unknown')}")
                    if health.get('Log'):
                        last_log = health['Log'][-1]
                        print(f"📝 Last check: {last_log.get('Output', 'N/A')[:200]}")
                
                # Ports
                ports = info.get('NetworkSettings', {}).get('Ports', {})
                if ports:
                    print(f"\n🔌 Ports:")
                    for port, bindings in ports.items():
                        if bindings:
                            print(f"  {port} -> {bindings[0].get('HostIp', '0.0.0.0')}:{bindings[0].get('HostPort', '')}")
                
                # Volumes
                mounts = info.get('Mounts', [])
                if mounts:
                    print(f"\n💾 Volumes:")
                    for mount in mounts[:3]:  # Show first 3 volumes
                        print(f"  {mount.get('Destination', '')} <- {mount.get('Source', '')}")
                
            except json.JSONDecodeError:
                print("❌ Failed to parse container info")
        else:
            print(f"❌ Container {container_name} not found")
    
    def export_json(self) -> str:
        """Export container status as JSON"""
        containers = self.get_all_containers()
        summary = self.check_health_summary()
        
        output = {
            'server': self.server_name,
            'timestamp': datetime.now().isoformat(),
            'docker_running': self.check_docker_service(),
            'summary': summary,
            'containers': containers
        }
        
        return json.dumps(output, indent=2)

def main():
    parser = argparse.ArgumentParser(
        description='Check Docker containers health status',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic check
  python3 check_docker.py
  
  # Verbose output
  python3 check_docker.py --verbose
  
  # Show all containers (including stopped)
  python3 check_docker.py --all
  
  # Check specific container
  python3 check_docker.py --container nginx
  
  # Export as JSON
  python3 check_docker.py --json
  
  # Specify server ID (for multi-server setup)
  python3 check_docker.py --server-id 1
  
  # Quick check (exit code only)
  python3 check_docker.py --quiet
        """
    )
    
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose output')
    parser.add_argument('--all', '-a', action='store_true', 
                       help='Show all containers (including stopped)')
    parser.add_argument('--container', '-c', type=str, 
                       help='Check specific container')
    parser.add_argument('--json', '-j', action='store_true', 
                       help='Export as JSON')
    parser.add_argument('--server-id', '-s', type=str, 
                       help='Server ID (for multi-server setup)')
    parser.add_argument('--quiet', '-q', action='store_true', 
                       help='Quiet mode (exit code only)')
    
    args = parser.parse_args()
    
    checker = DockerChecker(verbose=args.verbose, server_id=args.server_id)
    
    # Quick check mode
    if args.quiet:
        docker_ok = checker.check_docker_service()
        if not docker_ok:
            sys.exit(2)
        
        summary = checker.check_health_summary()
        if summary['problematic']:
            sys.exit(1)
        else:
            sys.exit(0)
    
    # JSON export
    if args.json:
        print(checker.export_json())
        sys.exit(0)
    
    # Check specific container
    if args.container:
        checker.check_specific_container(args.container)
        sys.exit(0)
    
    # Check Docker service
    if not checker.check_docker_service():
        print("❌ Docker service is NOT running!")
        print("\n💡 To start Docker:")
        print("  sudo systemctl start docker")
        print("  sudo systemctl enable docker")
        sys.exit(2)
    
    # Print summary
    is_healthy = checker.print_summary()
    
    # Show containers
    if args.all:
        containers = checker.get_all_containers()
    else:
        containers = checker.get_running_containers()
    
    if containers:
        checker.print_container_table(containers, show_all=args.all)
    
    # Exit with appropriate code
    if is_healthy:
        print("\n✅ All systems operational")
        sys.exit(0)
    else:
        print("\n⚠️ Some containers have issues")
        sys.exit(1)

if __name__ == '__main__':
    main()