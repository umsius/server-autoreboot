#!/usr/bin/env python3
import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from vm_manager import YandexCloudVMManager

load_dotenv()

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vm_restart.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация серверов из .env
SERVERS = [
    {
        'key': 'server1',
        'id': os.getenv('SERVER1_INSTANCE_ID'),
        'name': os.getenv('SERVER1_NAME', 'Server-01'),
        'ip': os.getenv('SERVER1_IP', 'Unknown IP')
    },
    {
        'key': 'server2',
        'id': os.getenv('SERVER2_INSTANCE_ID'),
        'name': os.getenv('SERVER2_NAME', 'Server-02'),
        'ip': os.getenv('SERVER2_IP', 'Unknown IP')
    },
    {
        'key': 'server3',
        'id': os.getenv('SERVER3_INSTANCE_ID'),
        'name': os.getenv('SERVER3_NAME', 'Server-03'),
        'ip': os.getenv('SERVER3_IP', 'Unknown IP')
    },
    {
        'key': 'server4',
        'id': os.getenv('SERVER4_INSTANCE_ID'),
        'name': os.getenv('SERVER4_NAME', 'Server-04'),
        'ip': os.getenv('SERVER4_IP', 'Unknown IP')
    }
]

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_ids = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
        self.bot = Bot(token=self.bot_token) if self.bot_token else None
    
    async def send_message(self, message: str):
        """Отправить сообщение всем админам"""
        if not self.bot:
            logger.error("Bot not initialized")
            return
        
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Message sent to {admin_id}")
                await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.error(f"Failed to send to {admin_id}: {e}")
    
    async def send_restart_notification(self, result: dict):
        """Отправить уведомление о результате перезагрузки"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if result['success']:
            status_emoji = "✅"
            status_text = "УСПЕШНО"
        else:
            status_emoji = "❌"
            status_text = "ОШИБКА"
        
        message = f"""{status_emoji} **Перезагрузка ВМ {status_text}** {status_emoji}

📅 Время: {current_time}
🖥️ Сервер: {result['vm_name']}
🌐 IP: {result['vm_ip']}
🆔 Instance ID: `{result['instance_id']}`

**Результат:** {status_text}
"""
        
        if result['errors']:
            message += f"\n**Ошибки:**\n"
            for error in result['errors']:
                message += f"• {error}\n"
        
        message += f"\n---\n_Перезагрузка выполнена через API Yandex Cloud_"
        
        await self.send_message(message)

async def restart_single_vm(server_config: dict, vm_manager: YandexCloudVMManager, notifier: TelegramNotifier):
    """Перезагрузить одну ВМ"""
    logger.info(f"Starting restart of {server_config['name']}")
    
    await notifier.send_message(
        f"🔔 **Начинается перезагрузка {server_config['name']}** 🔔\n\n"
        f"🖥️ {server_config['name']} ({server_config['ip']})\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    result = await vm_manager.restart_vm(
        instance_id=server_config['id'],
        vm_name=server_config['name'],
        vm_ip=server_config['ip']
    )
    
    await notifier.send_restart_notification(result)
    return result

async def restart_all_vms():
    """Перезагрузить все ВМ"""
    notifier = TelegramNotifier()
    vm_manager = YandexCloudVMManager(folder_id=os.getenv('YC_FOLDER_ID'))
    
    await notifier.send_message(
        "🔄 **Запущена плановая перезагрузка всех серверов** 🔄\n\n"
        f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📊 Всего серверов: {len(SERVERS)}"
    )
    
    results = []
    for server in SERVERS:
        if not server['id']:
            logger.warning(f"Skipping {server['key']} - no instance ID")
            continue
        
        result = await restart_single_vm(server, vm_manager, notifier)
        results.append(result)
        
        # Пауза между серверами
        if len(results) < len([s for s in SERVERS if s['id']]):
            await asyncio.sleep(300)  # 5 минут
    
    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    
    summary = f"""📊 **Итог плановой перезагрузки**

✅ Успешно: {success_count}
❌ Ошибок: {failed_count}
📅 Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    await notifier.send_message(summary)

async def restart_specific_vm(server_key: str):
    """Перезагрузить конкретную ВМ"""
    server_config = next((s for s in SERVERS if s['key'] == server_key), None)
    if not server_config:
        print(f"Server {server_key} not found")
        return
    
    notifier = TelegramNotifier()
    vm_manager = YandexCloudVMManager(folder_id=os.getenv('YC_FOLDER_ID'))
    await restart_single_vm(server_config, vm_manager, notifier)

if __name__ == '__main__':
    import sys
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--server' and len(sys.argv) > 2:
            asyncio.run(restart_specific_vm(sys.argv[2]))
        elif sys.argv[1] == '--all':
            asyncio.run(restart_all_vms())
        else:
            print("Usage:")
            print("  python main.py --all                    # Restart all VMs")
            print("  python main.py --server server1         # Restart specific VM")
    else:
        asyncio.run(restart_all_vms())