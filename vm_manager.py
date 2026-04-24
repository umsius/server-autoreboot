#!/usr/bin/env python3
import json
import asyncio
import logging
import socket
import subprocess
import time
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

class YandexCloudVMManager:
    """Управление виртуальными машинами в Yandex Cloud через API"""
    
    def __init__(self, folder_id: str, key_file: str = 'key.json'):
        self.folder_id = folder_id
        self.key_file = key_file
        # Загрузка JSON-ключа сервисного аккаунта
        with open(key_file, 'r') as f:
            sa_key = json.load(f)
        self.sdk = yandexcloud.SDK(service_account_key=sa_key)
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
    
    def stop_instance(self, instance_id: str, retry: int = 3) -> Tuple[bool, Optional[str]]:
        """Остановить ВМ с повторными попытками"""
        for attempt in range(retry):
            try:
                self.logger.info(f"Stopping instance {instance_id} (attempt {attempt + 1})")
                request = StopInstanceRequest(instance_id=instance_id)
                operation = self.instance_service.Stop(request)
                self.sdk.wait_operation_and_get_result(operation, timeout=120)
                self.logger.info(f"Instance {instance_id} stopped successfully")
                return True, None
            except Exception as e:
                error_msg = str(e)
                if "FAILED_PRECONDITION" in error_msg and attempt < retry - 1:
                    self.logger.warning(f"Stop operation in progress, waiting 30 seconds and retrying...")
                    time.sleep(30)
                    continue
                self.logger.error(f"Failed to stop instance {instance_id}: {error_msg}")
                return False, error_msg
        return False, "Max retries exceeded"

    def start_instance(self, instance_id: str, retry: int = 3) -> Tuple[bool, Optional[str]]:
        """Запустить ВМ с повторными попытками"""
        for attempt in range(retry):
            try:
                self.logger.info(f"Starting instance {instance_id} (attempt {attempt + 1})")
                request = StartInstanceRequest(instance_id=instance_id)
                operation = self.instance_service.Start(request)
                self.sdk.wait_operation_and_get_result(operation, timeout=300)
                self.logger.info(f"Instance {instance_id} started successfully")
                return True, None
            except Exception as e:
                error_msg = str(e)
                if "FAILED_PRECONDITION" in error_msg and attempt < retry - 1:
                    self.logger.warning(f"Start operation in progress, waiting 30 seconds and retrying...")
                    time.sleep(30)
                    continue
                self.logger.error(f"Failed to start instance {instance_id}: {error_msg}")
                return False, error_msg
        return False, "Max retries exceeded"
    
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
    
    def wait_for_server_ready(self, ip: str, timeout: int = 120) -> bool:
        """
        Ожидать, пока сервер станет доступным (таймаут 2 минуты).
        Проверяет сначала ping, затем TCP порт 22 (SSH).
        Возвращает True, если сервер доступен.
        """
        start_time = time.time()
        check_count = 0
        
        self.logger.info(f"Starting readiness check for {ip} (timeout: {timeout}s)")
        
        while (time.time() - start_time) < timeout:
            check_count += 1
            
            if self.check_ping(ip):
                self.logger.info(f"✅ {ip} is responding to ping (check #{check_count})")
                
                if self.check_tcp_port(ip, port=22, timeout=5):
                    self.logger.info(f"✅ {ip}:22 is open (SSH ready)")
                    return True
                else:
                    self.logger.info(f"⏳ {ip} responds to ping but port 22 not ready yet")
            else:
                self.logger.info(f"⏳ Waiting for {ip} to become available... (check #{check_count})")
            
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
            'key_file': self.key_file,
            'start_time': datetime.now().isoformat(),
            'end_time': None,
            'errors': []
        }
        
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
        
        self.logger.info(f"Stopping {vm_name}...")
        if notifier:
            await notifier.update_status(vm_name, "stopping", "⏸️")
        
        success, error = self.stop_instance(instance_id)
        if not success:
            result['errors'].append(f"Stop failed: {error}")
            if notifier:
                await notifier.update_status(vm_name, "error", "❌")
            return result
        
        self.logger.info(f"{vm_name} stopped successfully")
        
        await asyncio.sleep(10)
        
        self.logger.info(f"Starting {vm_name}...")
        if notifier:
            await notifier.update_status(vm_name, "starting", "▶️")
        
        success, error = self.start_instance(instance_id)
        if not success:
            result['errors'].append(f"Start failed: {error}")
            if notifier:
                await notifier.update_status(vm_name, "error", "❌")
            return result
        
        self.logger.info(f"{vm_name} started successfully")
        
        self.logger.info(f"Waiting for {vm_name} ({vm_ip}) to become available...")
        if notifier:
            await notifier.update_status(vm_name, "waiting", "⏳")
        
        loop = asyncio.get_event_loop()
        is_ready = await loop.run_in_executor(
            None, 
            self.wait_for_server_ready, 
            vm_ip, 
            120
        )
        
        if not is_ready:
            result['errors'].append(f"Server {vm_ip} did not become ready within 2 minutes")
            if notifier:
                await notifier.update_status(vm_name, "error", "❌")
            return result
        
        self.logger.info(f"{vm_name} is now available")
        if notifier:
            await notifier.update_status(vm_name, "ready", "✅")
        
        await asyncio.sleep(10)
        
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