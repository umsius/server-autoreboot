#!/usr/bin/env python3
import os
import sys
import subprocess
import asyncio
import logging
import socket
from datetime import datetime
from typing import List, Tuple
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'/var/log/server_reboot_{os.getenv("SERVER_ID", "unknown")}.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ServerRebootNotifier:
    def __init__(self, config_path: str):
        # Load specific server config
        if not os.path.exists(config_path):
            logger.error(f"Config file not found: {config_path}")
            sys.exit(1)
        
        load_dotenv(config_path)
        
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_ids = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
        self.server_name = os.getenv('SERVER_NAME', socket.gethostname())
        self.server_ip = os.getenv('SERVER_IP', self.get_server_ip())
        self.server_id = os.getenv('SERVER_ID', 'unknown')
        self.services_to_check = os.getenv('SERVICES_TO_CHECK', '').split(',')
        
        if not self.bot_token:
            logger.error("BOT_TOKEN not found in config file")
            sys.exit(1)
        
        self.bot = Bot(token=self.bot_token)
    
    def get_server_ip(self) -> str:
        """Get server IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "Unknown IP"
    
    async def send_message_to_admins(self, message: str):
        """Send message to all admins"""
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(
                    chat_id=admin_id, 
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Message sent to admin {admin_id}")
                await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.error(f"Failed to send message to {admin_id}: {e}")
    
    def check_docker_containers(self) -> Tuple[bool, str]:
        """Check if all docker containers are running"""
        docker_enabled = os.getenv('DOCKER_CHECK_ENABLED', 'true').lower() == 'true'
        
        if not docker_enabled:
            return True, "Docker check disabled"
        
        try:
            result = subprocess.run(
                ['docker', 'ps', '--format', '{{.Names}}|{{.Status}}'],
                capture_output=True,
                text=True,
                timeout=int(os.getenv('DOCKER_CHECK_TIMEOUT', '30'))
            )
            
            if result.returncode != 0:
                return False, "Docker command failed"
            
            containers = result.stdout.strip().split('\n')
            if not containers or containers == ['']:
                return True, "No containers running"
            
            problematic_containers = []
            for container in containers:
                if '|' in container:
                    name, status = container.split('|', 1)
                    if 'unhealthy' in status.lower() or 'exited' in status.lower():
                        problematic_containers.append(f"{name} ({status})")
            
            if problematic_containers:
                return False, f"⚠️ Problematic containers: {', '.join(problematic_containers)}"
            else:
                return True, f"✅ All {len(containers)} containers are healthy"
                
        except subprocess.TimeoutExpired:
            return False, "Docker check timeout"
        except FileNotFoundError:
            return True, "Docker not installed"
        except Exception as e:
            return False, f"Docker check error: {str(e)}"
    
    def check_system_services(self) -> List[str]:
        """Check system services status"""
        if not self.services_to_check or self.services_to_check == ['']:
            return []
        
        failed_services = []
        for service in self.services_to_check:
            try:
                result = subprocess.run(
                    ['systemctl', 'is-active', service.strip()],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode != 0 or 'active' not in result.stdout:
                    failed_services.append(service.strip())
            except Exception as e:
                failed_services.append(f"{service} (check error: {str(e)})")
        
        return failed_services
    
    async def send_reboot_notification(self, docker_status: str, service_status: str = ""):
        """Send reboot notification to admins"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"""🔄 **Сервер перезагружен** 🔄

📅 Время: {current_time}
🆔 Сервер #{self.server_id}
🖥️ Название: {self.server_name}
🌐 IP: {self.server_ip}

✅ Перезагрузка выполнена по плановому заданию (каждые 24 часа в 08:55)

🐳 **Проверка Docker контейнеров:**
{docker_status}

{service_status}
---
_Автоматическое уведомление от системы мониторинга #{self.server_id}_"""
        
        await self.send_message_to_admins(message)
    
    async def reboot_server(self):
        """Reboot the server"""
        try:
            logger.info(f"Server {self.server_name} ({self.server_ip}) - Starting reboot process...")
            
            # Check docker before reboot
            docker_ok, docker_message = self.check_docker_containers()
            pre_reboot_status = "✅ Всё доступно" if docker_ok else f"⚠️ {docker_message}"
            
            # Send pre-reboot notification
            pre_reboot_msg = f"""🔔 **Подготовка к перезагрузке сервера #{self.server_id}** 🔔

🖥️ {self.server_name} ({self.server_ip})
⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

🐳 Состояние Docker перед перезагрузкой:
{pre_reboot_status}

Сервер будет перезагружен через 10 секунд..."""
            
            await self.send_message_to_admins(pre_reboot_msg)
            
            # Wait 10 seconds before reboot
            await asyncio.sleep(10)
            
            # Send final notification before reboot
            final_msg = f"⚠️ **Сервер #{self.server_id} {self.server_name} ({self.server_ip}) перезагружается...** ⚠️"
            await self.send_message_to_admins(final_msg)
            
            # Perform reboot
            logger.info(f"Executing system reboot on {self.server_name}")
            subprocess.run(['sudo', '/sbin/reboot'], check=True)
            
        except Exception as e:
            error_msg = f"❌ **Ошибка при перезагрузке сервера #{self.server_id}** ❌\n\n{self.server_name} ({self.server_ip})\nОшибка: {str(e)}"
            await self.send_message_to_admins(error_msg)
            logger.error(f"Reboot failed: {e}")
            sys.exit(1)
    
    async def check_after_reboot(self):
        """Check system status after reboot"""
        await asyncio.sleep(30)  # Wait for services to start
        
        # Check docker containers after reboot
        docker_ok, docker_message = self.check_docker_containers()
        
        if docker_ok:
            docker_status = "✅ Всё доступно"
        else:
            docker_status = f"⚠️ Есть проблема: {docker_message}"
        
        # Check system services
        failed_services = self.check_system_services()
        service_status = ""
        if failed_services:
            service_status = f"⚠️ **Проблемные сервисы:**\n{', '.join(failed_services)}"
        else:
            service_status = "✅ Все системные сервисы работают"
        
        await self.send_reboot_notification(docker_status, service_status)
        
        # Additional system checks
        try:
            # Check disk space
            df_result = subprocess.run(['df', '-h', '/'], capture_output=True, text=True)
            disk_info = df_result.stdout.split('\n')[1] if df_result.stdout else "N/A"
            
            # Check memory
            free_result = subprocess.run(['free', '-h'], capture_output=True, text=True)
            mem_lines = free_result.stdout.split('\n')
            mem_info = mem_lines[1] if len(mem_lines) > 1 else "N/A"
            
            # Check load average
            load_result = subprocess.run(['uptime'], capture_output=True, text=True)
            load_info = load_result.stdout.strip()
            
            status_message = f"""📊 **Статус сервера #{self.server_id} после перезагрузки**

🖥️ {self.server_name} ({self.server_ip})

💾 Дисковое пространство (/) :
{disk_info}

🧠 Память:
{mem_info}

📈 Load Average:
{load_info}

🐳 Docker: {docker_status}

🛠️ Сервисы: {service_status}

✅ Система работает штатно"""
            
            await self.send_message_to_admins(status_message)
            
        except Exception as e:
            logger.error(f"Failed to get system status: {e}")

def main():
    if len(sys.argv) < 2:
        print("Usage: reboot_service.py <config_path> [--check-after-reboot]")
        sys.exit(1)
    
    config_path = sys.argv[1]
    notifier = ServerRebootNotifier(config_path)
    
    # Check if this is a post-reboot check
    if len(sys.argv) > 2 and sys.argv[2] == '--check-after-reboot':
        asyncio.run(notifier.check_after_reboot())
    else:
        # Perform reboot
        asyncio.run(notifier.reboot_server())

if __name__ == '__main__':
    main()