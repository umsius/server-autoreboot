#!/usr/bin/env python3
import json
import asyncio
import logging
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
    
    async def restart_vm(self, instance_id: str, vm_name: str, vm_ip: str) -> Dict:
        """Перезагрузить ВМ (Stop + Start)"""
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
        success, error = self.stop_instance(instance_id)
        if not success:
            result['errors'].append(f"Stop failed: {error}")
            return result
        
        self.logger.info(f"{vm_name} stopped successfully")
        
        # Ждем перед запуском
        await asyncio.sleep(10)
        
        # Запускаем ВМ
        self.logger.info(f"Starting {vm_name}...")
        success, error = self.start_instance(instance_id)
        if not success:
            result['errors'].append(f"Start failed: {error}")
            return result
        
        self.logger.info(f"{vm_name} started successfully")
        
        # Ждем загрузки ВМ
        await asyncio.sleep(60)
        
        # Проверяем финальный статус
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