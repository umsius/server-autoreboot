#!/usr/bin/env python3
import json
import asyncio
import logging
import socket
import subprocess
from datetime import datetime
from typing import Dict, Optional, Tuple
import yandexcloud
from yandex.cloud.compute.v1.instance_service_pb2_grpc import InstanceServiceStub
from yandex.cloud.compute.v1.instance_service_pb2 import (
    StopInstanceRequest,
    StartInstanceRequest,
    GetInstanceRequest
)
from yandex.cloud.compute.v1.instance_pb2 import Instance

# Загрузка JSON-ключа сервисного аккаунта
with open('key.json', 'r') as f:
    SA_KEY = json.load(f)

class YandexCloudVMManager:
    """Управление виртуальными машинами в Yandex Cloud через API"""
    
    def __init__(self, folder_id: str):
        self.folder_id = folder_id
        self.sdk = yandexcloud.SDK(service_account_key=SA_KEY)
        self.instance_service = self.sdk.client(InstanceServiceStub)
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
    
    def get_instance_status(self, instance_id: str) -> Tuple[Optional[str], Optional[str]]:
        """Получить статус ВМ"""
        try:
            request = GetInstanceRequest(instance_id=instance_id)
            instance = self.instance_service.Get(request)
            
            status_map = {
                Instance.Status.PROVISIONING: "PROVISIONING",
                Instance.Status.RUNNING: "RUNNING",
                Instance.Status.STOPPING: "STOPPING", 
                Instance.Status.STOPPED: "STOPPED",
                Instance.Status.STARTING: "STARTING",
                Instance.Status.RESTARTING: "RESTARTING",
                Instance.Status.ERROR: "ERROR",
            }
            
            status = status_map.get(instance.status, "UNKNOWN")
            self.logger.info(f"Instance {instance_id} status: {status}")
            return status, None
            
        except Exception as e:
            self.logger.error(f"Error getting status for {instance_id}: {e}")
            return None, str(e)
    
    def stop_instance(self, instance_id: str) -> Tuple[bool, Optional[str]]:
        """Остановить ВМ"""
        try:
            self.logger.info(f"Stopping instance {instance_id}")
            request = StopInstanceRequest(instance_id=instance_id)
            
            # Используем встроенный метод SDK для ожидания
            operation = self.instance_service.Stop(request)
            
            # Принудительно ожидаем завершения операции через SDK
            self.sdk.wait_operation_and_get_result(operation, timeout=120)
            
            self.logger.info(f"Instance {instance_id} stopped successfully")
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to stop instance {instance_id}: {error_msg}")
            return False, error_msg
    
    def start_instance(self, instance_id: str) -> Tuple[bool, Optional[str]]:
        """Запустить ВМ"""
        try:
            self.logger.info(f"Starting instance {instance_id}")
            request = StartInstanceRequest(instance_id=instance_id)
            
            # Используем встроенный метод SDK для ожидания
            operation = self.instance_service.Start(request)
            
            # Принудительно ожидаем завершения операции через SDK
            self.sdk.wait_operation_and_get_result(operation, timeout=300)
            
            self.logger.info(f"Instance {instance_id} started successfully")
            return True, None
            
        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Failed to start instance {instance_id}: {error_msg}")
            return False, error_msg
    
    def check_tcp_port(self, ip: str, port: int = 22, timeout: int = 5) -> bool:
        """Проверить доступность TCP порта на сервере"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except Exception as e:
            self.logger.debug(f"TCP check failed for {ip}:{port} - {e}")
            return False
    
    def check_ping(self, ip: str) -> bool:
        """Проверить доступность сервера по ICMP ping"""
        try:
            result = subprocess.run(
                ['ping', '-c', '1', '-W', '2', ip],
                capture_output=True,
                timeout=3
            )
            return result.returncode == 0
        except Exception as e:
            self.logger.debug(f"Ping check failed for {ip}: {e}")
            return False
    
    def wait_for_server_ready(self, ip: str, timeout: int = 300) -> bool:
        """
        Ожидать, пока сервер станет доступным.
        Проверяет сначала ping, затем TCP порт 22 (SSH).
        Возвращает True, если сервер доступен.
        """
        import time
        
        start_time = time.time()
        check_count = 0
        
        self.logger.info(f"Starting readiness check for {ip} (timeout: {timeout}s)")
        
        while (time.time() - start_time) < timeout:
            check_count += 1
            
            # Шаг 1: Проверяем ping
            if self.check_ping(ip):
                self.logger.info(f"✅ {ip} is responding to ping (check #{check_count})")
                
                # Шаг 2: Проверяем TCP порт 22 (SSH)
                if self.check_tcp_port(ip, port=22, timeout=5):
                    self.logger.info(f"✅ {ip}:22 is open (SSH ready)")
                    return True
                else:
                    self.logger.info(f"⏳ {ip} responds to ping but port 22 not ready yet")
            else:
                self.logger.info(f"⏳ Waiting for {ip} to become available... (check #{check_count})")
            
            # Ждем 10 секунд перед следующей проверкой
            time.sleep(10)
        
        self.logger.error(f"❌ Server {ip} did not become ready within {timeout}s")
        return False
    
    async def restart_vm(self, instance_id: str, vm_name: str, vm_ip: str, notifier=None) -> Dict:
        """
        Перезагрузить ВМ (Stop + Start) с проверкой доступности.
        notifier - объект TelegramNotifier для отправки промежуточных уведомлений
        """
        result = {
            'success': False,
            'vm_name': vm_name,
            'vm_ip': vm_ip,
            'instance_id': instance_id,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
        # Проверяем текущий статус
        status, error = self.get_instance_status(instance_id)
        if error:
            result['errors'].append(f"Failed to get status: {error}")
            return result
        
        self.logger.info(f"Current status of {vm_name}: {status}")
        
        if status == "STOPPED":
            result['errors'].append(f"VM is already stopped")
            return result
        
        if status != "RUNNING":
            result['errors'].append(f"VM is in {status} state, cannot restart")
            return result
        
        # Останавливаем ВМ
        self.logger.info(f"Stopping {vm_name}...")
        if notifier:
            await notifier.send_message(f"⏸️ Останавливаем {vm_name}...")
        
        success, error = self.stop_instance(instance_id)
        if not success:
            result['errors'].append(f"Stop failed: {error}")
            return result
        
        self.logger.info(f"{vm_name} stopped successfully")
        
        # Ждем 10 секунд перед запуском
        await asyncio.sleep(10)
        
        # Запускаем ВМ
        self.logger.info(f"Starting {vm_name}...")
        if notifier:
            await notifier.send_message(f"▶️ Запускаем {vm_name}...")
        
        success, error = self.start_instance(instance_id)
        if not success:
            result['errors'].append(f"Start failed: {error}")
            return result
        
        self.logger.info(f"{vm_name} started successfully")
        
        # Ожидаем доступности сервера
        self.logger.info(f"Waiting for {vm_name} ({vm_ip}) to become available...")
        if notifier:
            await notifier.send_message(
                f"⏳ Ожидаем доступности {vm_name} ({vm_ip})...\n"
                f"Это может занять до 5 минут."
            )
        
        # Проверяем доступность в отдельном потоке (чтобы не блокировать асинхронность)
        loop = asyncio.get_event_loop()
        is_ready = await loop.run_in_executor(
            None, 
            self.wait_for_server_ready, 
            vm_ip, 
            300  # 5 минут таймаут
        )
        
        if not is_ready:
            result['errors'].append(f"Server {vm_ip} did not become ready within timeout")
            if notifier:
                await notifier.send_message(
                    f"⚠️ **ВНИМАНИЕ!**\n"
                    f"Сервер {vm_name} запущен, но не отвечает на запросы.\n"
                    f"Проверьте статус вручную."
                )
        else:
            self.logger.info(f"{vm_name} is now available")
            if notifier:
                await notifier.send_message(f"✅ {vm_name} доступен и отвечает на запросы")
            
            # Дополнительная пауза для стабилизации сервисов
            self.logger.info(f"Waiting additional 30 seconds for services to stabilize...")
            await asyncio.sleep(30)
        
        # Проверяем финальный статус ВМ
        final_status, error = self.get_instance_status(instance_id)
        if error:
            result['errors'].append(f"Final status check failed: {error}")
        elif final_status == "RUNNING":
            result['success'] = True
            self.logger.info(f"{vm_name} restart completed successfully")
        else:
            result['errors'].append(f"Final status is {final_status}, not RUNNING")
        
        result['end_time'] = datetime.now().isoformat()
        return result