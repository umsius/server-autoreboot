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

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/vm_restart.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Конфигурация серверов из .env с указанием ключа для каждого сервера
SERVERS = [
    {
        'key': 'server1',
        'id': os.getenv('SERVER1_INSTANCE_ID'),
        'name': os.getenv('SERVER1_NAME', 'Server-01'),
        'ip': os.getenv('SERVER1_IP', 'Unknown IP'),
        'key_file': os.getenv('SERVER1_KEY_FILE', 'key.json'),
        'folder_id': os.getenv('SERVER1_FOLDER_ID', os.getenv('YC_FOLDER_ID'))
    },
    {
        'key': 'server2',
        'id': os.getenv('SERVER2_INSTANCE_ID'),
        'name': os.getenv('SERVER2_NAME', 'Server-02'),
        'ip': os.getenv('SERVER2_IP', 'Unknown IP'),
        'key_file': os.getenv('SERVER2_KEY_FILE', 'key.json'),
        'folder_id': os.getenv('SERVER2_FOLDER_ID', os.getenv('YC_FOLDER_ID'))
    },
    {
        'key': 'server3',
        'id': os.getenv('SERVER3_INSTANCE_ID'),
        'name': os.getenv('SERVER3_NAME', 'Server-03'),
        'ip': os.getenv('SERVER3_IP', 'Unknown IP'),
        'key_file': os.getenv('SERVER3_KEY_FILE', 'key.json'),
        'folder_id': os.getenv('SERVER3_FOLDER_ID', os.getenv('YC_FOLDER_ID'))
    },
    {
        'key': 'server4',
        'id': os.getenv('SERVER4_INSTANCE_ID'),
        'name': os.getenv('SERVER4_NAME', 'Server-04'),
        'ip': os.getenv('SERVER4_IP', 'Unknown IP'),
        'key_file': os.getenv('SERVER4_KEY_FILE', 'key.json'),
        'folder_id': os.getenv('SERVER4_FOLDER_ID', os.getenv('YC_FOLDER_ID'))
    }
]

class TelegramNotifier:
    def __init__(self):
        self.bot_token = os.getenv('BOT_TOKEN')
        self.admin_ids = [int(x.strip()) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
        self.bot = Bot(token=self.bot_token) if self.bot_token else None
        self.status_messages = {}
    
    async def send_start_notification(self, server_name: str, server_ip: str, instance_id: str):
        if not self.bot or not self.admin_ids:
            return None
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"""🔄 **Перезагрузка сервера** 🔄

🖥️ **{server_name}** ({server_ip})
🆔 `{instance_id}`
⏰ Время: {current_time}

⏸️ **Статус:** Останавливаем сервер..."""
        
        try:
            msg = await self.bot.send_message(
                chat_id=self.admin_ids[0],
                text=message,
                parse_mode='Markdown'
            )
            self.status_messages[server_name] = msg.message_id
            logger.info(f"Start notification sent for {server_name}")
            return msg
        except TelegramError as e:
            logger.error(f"Failed to send start notification: {e}")
            return None
    
    async def update_status(self, server_name: str, status: str, emoji: str = "⏳"):
        message_id = self.status_messages.get(server_name)
        if not message_id or not self.bot or not self.admin_ids:
            return
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        messages_map = {
            "stopping": "⏸️ Останавливаем сервер...",
            "starting": "▶️ Запускаем сервер...",
            "waiting": "⏳ Ожидаем доступности сервера...\n(Это может занять до 2 минут)",
            "ready": "✅ Сервер доступен и отвечает на запросы",
            "error": "❌ Ошибка при перезагрузке"
        }
        
        status_text = messages_map.get(status, status)
        
        message = f"""🔄 **Перезагрузка сервера** 🔄

🖥️ **{server_name}**
⏰ Время: {current_time}

{emoji} **Статус:** {status_text}"""
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.admin_ids[0],
                message_id=message_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Status updated for {server_name}: {status}")
        except TelegramError as e:
            logger.error(f"Failed to update status for {server_name}: {e}")
    
    async def send_final_notification(self, server_name: str, server_ip: str, instance_id: str, success: bool, errors: list = None, duration: str = None):
        message_id = self.status_messages.get(server_name)
        if not message_id or not self.bot or not self.admin_ids:
            return
        
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        if success:
            status_emoji = "✅"
            status_text = "УСПЕШНО ЗАВЕРШЕНА"
            result_text = f"""✅ **Результат:** УСПЕШНО
{duration if duration else ''}
✅ Все сервисы работают нормально"""
        else:
            status_emoji = "❌"
            status_text = "ОШИБКА"
            error_text = "\n".join([f"• {e}" for e in errors]) if errors else "Неизвестная ошибка"
            result_text = f"""❌ **Результат:** ОШИБКА

**Ошибки:**
{error_text}"""
        
        message = f"""{status_emoji} **Перезагрузка сервера {status_text}** {status_emoji}

🖥️ **{server_name}** ({server_ip})
🆔 `{instance_id}`
⏰ Время: {current_time}

{result_text}

---
_Перезагрузка выполнена через API Yandex Cloud_"""
        
        try:
            await self.bot.edit_message_text(
                chat_id=self.admin_ids[0],
                message_id=message_id,
                text=message,
                parse_mode='Markdown'
            )
            logger.info(f"Final notification sent for {server_name}")
        except TelegramError as e:
            logger.error(f"Failed to send final notification: {e}")
    
    async def send_broadcast_message(self, message: str):
        if not self.bot:
            return
        
        for admin_id in self.admin_ids:
            try:
                await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Broadcast message sent to {admin_id}")
                await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.error(f"Failed to send broadcast to {admin_id}: {e}")
    
    async def send_pause_notification(self, server_name: str, next_server_name: str, duration: int = 120):
        message = f"""⏳ **Пауза между перезагрузками**

✅ Сервер **{server_name}** перезагружен
⏰ Следующий сервер (**{next_server_name}**) будет перезагружен через {duration // 60} минут

_Сообщение будет автоматически удалено через {duration // 60} минут_"""
        
        messages = []
        for admin_id in self.admin_ids:
            try:
                msg = await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                messages.append({'admin_id': admin_id, 'message_id': msg.message_id})
                logger.info(f"Pause notification sent to {admin_id}")
                await asyncio.sleep(0.5)
            except TelegramError as e:
                logger.error(f"Failed to send pause notification to {admin_id}: {e}")
        
        async def delete_messages():
            await asyncio.sleep(duration)
            for item in messages:
                try:
                    await self.bot.delete_message(
                        chat_id=item['admin_id'],
                        message_id=item['message_id']
                    )
                    logger.info(f"Pause message deleted for admin {item['admin_id']}")
                except TelegramError as e:
                    logger.error(f"Failed to delete pause message: {e}")
        
        asyncio.create_task(delete_messages())

async def restart_single_vm(server_config: dict, notifier: TelegramNotifier):
    """Перезагрузить одну ВМ с обновлением статуса"""
    server_name = server_config['name']
    logger.info(f"Starting restart of {server_name}")
    
    if not server_config['folder_id']:
        logger.error(f"No folder_id for {server_name}")
        await notifier.send_broadcast_message(f"❌ Ошибка: Не указан folder_id для сервера {server_name}")
        return False
    
    # Проверяем, какой ключ используется для логирования
    logger.info(f"Using key_file: {server_config['key_file']} for {server_name}")
    
    vm_manager = YandexCloudVMManager(
        folder_id=server_config['folder_id'],
        key_file=server_config['key_file']
    )
    
    await notifier.send_start_notification(
        server_name=server_name,
        server_ip=server_config['ip'],
        instance_id=server_config['id']
    )
    
    start_time = datetime.now()
    
    await notifier.update_status(server_name, "stopping", "⏸️")
    
    success, error = vm_manager.stop_instance(server_config['id'])
    if not success:
        await notifier.update_status(server_name, "error", "❌")
        await notifier.send_final_notification(
            server_name=server_name,
            server_ip=server_config['ip'],
            instance_id=server_config['id'],
            success=False,
            errors=[f"Остановка не удалась: {error}"]
        )
        return False
    
    await notifier.update_status(server_name, "starting", "▶️")
    
    success, error = vm_manager.start_instance(server_config['id'])
    if not success:
        await notifier.update_status(server_name, "error", "❌")
        await notifier.send_final_notification(
            server_name=server_name,
            server_ip=server_config['ip'],
            instance_id=server_config['id'],
            success=False,
            errors=[f"Запуск не удался: {error}"]
        )
        return False
    
    await notifier.update_status(server_name, "waiting", "⏳")
    
    is_ready = vm_manager.wait_for_server_ready(server_config['ip'], timeout=120)
    
    if not is_ready:
        await notifier.update_status(server_name, "error", "❌")
        await notifier.send_final_notification(
            server_name=server_name,
            server_ip=server_config['ip'],
            instance_id=server_config['id'],
            success=False,
            errors=[f"Сервер не стал доступен за 2 минуты"]
        )
        return False
    
    await notifier.update_status(server_name, "ready", "✅")
    
    await asyncio.sleep(10)
    
    end_time = datetime.now()
    duration = end_time - start_time
    duration_str = f"⏱️ **Длительность:** {duration.seconds // 60} мин {duration.seconds % 60} сек"
    
    await notifier.send_final_notification(
        server_name=server_name,
        server_ip=server_config['ip'],
        instance_id=server_config['id'],
        success=True,
        duration=duration_str
    )
    
    return True

async def restart_all_vms():
    """Перезагрузить все ВМ по очереди"""
    notifier = TelegramNotifier()
    
    active_servers = [s for s in SERVERS if s['id']]
    
    await notifier.send_broadcast_message(
        "🔄 **Запущена плановая перезагрузка всех серверов** 🔄\n\n"
        f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📊 Всего серверов: {len(active_servers)}\n\n"
        f"Перезагрузка будет выполнена последовательно."
    )
    
    results = []
    
    for i, server in enumerate(active_servers, 1):
        logger.info(f"Processing server {i}/{len(active_servers)}: {server['name']}")
        
        success = await restart_single_vm(server, notifier)
        results.append({'server': server['name'], 'success': success})
        
        if i < len(active_servers):
            await notifier.send_pause_notification(
                server_name=server['name'],
                next_server_name=active_servers[i]['name'],
                duration=120
            )
    
    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    
    summary = f"""📊 **Итог плановой перезагрузки**

✅ Успешно: {success_count}
❌ Ошибок: {failed_count}
📅 Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"""
    
    if failed_count > 0:
        summary += "\n\n**Серверы с ошибками:**\n"
        for r in results:
            if not r['success']:
                summary += f"• {r['server']}\n"
    
    await notifier.send_broadcast_message(summary)

async def restart_specific_vm(server_key: str):
    """Перезагрузить конкретную ВМ по ключу"""
    server_config = next((s for s in SERVERS if s['key'] == server_key), None)
    if not server_config:
        print(f"Server {server_key} not found")
        return
    
    if not server_config['id']:
        print(f"Server {server_key} has no instance ID configured")
        return
    
    notifier = TelegramNotifier()
    
    await notifier.send_broadcast_message(
        f"🔧 **Ручная перезагрузка сервера** 🔧\n\n"
        f"🖥️ **{server_config['name']}** ({server_config['ip']})\n"
        f"👤 Инициатор: Администратор\n"
        f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    )
    
    await restart_single_vm(server_config, notifier)

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
            print("  python main.py --server server2         # Restart specific VM")
            print("  python main.py --server server3         # Restart specific VM")
            print("  python main.py --server server4         # Restart specific VM")
    else:
        asyncio.run(restart_all_vms())