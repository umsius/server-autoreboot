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
        self.status_messages = {}  # Храним ID сообщений для каждого сервера
    
    async def send_message(self, message: str):
        """Отправить новое сообщение всем админам"""
        if not self.bot:
            logger.error("Bot not initialized")
            return
        
        for admin_id in self.admin_ids:
            try:
                msg = await self.bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode='Markdown'
                )
                logger.info(f"Message sent to {admin_id}")
                return msg
            except TelegramError as e:
                logger.error(f"Failed to send to {admin_id}: {e}")
        return None
    
    async def edit_message(self, message_id: int, text: str):
        """Отредактировать существующее сообщение"""
        if not self.bot:
            return
        
        for admin_id in self.admin_ids:
            try:
                await self.bot.edit_message_text(
                    chat_id=admin_id,
                    message_id=message_id,
                    text=text,
                    parse_mode='Markdown'
                )
                logger.info(f"Message {message_id} edited")
            except TelegramError as e:
                logger.error(f"Failed to edit message {message_id}: {e}")
    
    async def send_start_notification(self, server_name: str, server_ip: str, instance_id: str):
        """Отправить начальное сообщение и сохранить его ID"""
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        message = f"""🔄 **Перезагрузка сервера** 🔄

🖥️ **{server_name}** ({server_ip})
🆔 `{instance_id}`
⏰ Время: {current_time}

⏸️ **Статус:** Останавливаем сервер..."""
        
        msg = await self.send_message(message)
        if msg:
            self.status_messages[server_name] = msg.message_id
        return msg
    
    async def update_status(self, server_name: str, status: str, emoji: str = "⏳"):
        """Обновить статус в сообщении"""
        message_id = self.status_messages.get(server_name)
        if not message_id:
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
        
        await self.edit_message(message_id, message)
    
    async def send_final_notification(self, server_name: str, server_ip: str, instance_id: str, success: bool, errors: list = None, duration: str = None):
        """Отправить финальное сообщение о результате"""
        message_id = self.status_messages.get(server_name)
        if not message_id:
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
        
        await self.edit_message(message_id, message)
    
    async def send_pause_notification(self, server_name: str, next_server_name: str, duration: int = 120):
        """Отправить уведомление о паузе между серверами"""
        message = f"""⏳ **Пауза между перезагрузками**

✅ Сервер **{server_name}** перезагружен
⏰ Следующий сервер (**{next_server_name}**) будет перезагружен через {duration // 60} минут

_Сообщение будет автоматически удалено через {duration // 60} минут_"""
        
        msg = await self.send_message(message)
        
        # Удаляем сообщение через duration секунд
        if msg:
            await asyncio.sleep(duration)
            try:
                for admin_id in self.admin_ids:
                    await self.bot.delete_message(chat_id=admin_id, message_id=msg.message_id)
                    logger.info(f"Pause message deleted for {server_name}")
            except TelegramError as e:
                logger.error(f"Failed to delete pause message: {e}")

async def restart_single_vm(server_config: dict, vm_manager: YandexCloudVMManager, notifier: TelegramNotifier):
    """Перезагрузить одну ВМ с обновлением статуса"""
    server_name = server_config['name']
    logger.info(f"Starting restart of {server_name}")
    
    # Отправляем начальное сообщение
    await notifier.send_start_notification(
        server_name=server_name,
        server_ip=server_config['ip'],
        instance_id=server_config['id']
    )
    
    start_time = datetime.now()
    
    # Обновляем статус: остановка
    await notifier.update_status(server_name, "stopping", "⏸️")
    
    # Останавливаем ВМ
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
    
    # Обновляем статус: запуск
    await notifier.update_status(server_name, "starting", "▶️")
    
    # Запускаем ВМ
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
    
    # Обновляем статус: ожидание
    await notifier.update_status(server_name, "waiting", "⏳")
    
    # Ожидаем доступности сервера (2 минуты = 120 секунд)
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
    
    # Обновляем статус: готов
    await notifier.update_status(server_name, "ready", "✅")
    
    # Дополнительная пауза для стабилизации (10 секунд)
    await asyncio.sleep(10)
    
    # Финальное сообщение
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
    vm_manager = YandexCloudVMManager(folder_id=os.getenv('YC_FOLDER_ID'))
    
    # Отправляем общее сообщение о начале
    await notifier.send_message(
        "🔄 **Запущена плановая перезагрузка всех серверов** 🔄\n\n"
        f"📅 Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"📊 Всего серверов: {len([s for s in SERVERS if s['id']])}\n\n"
        f"Перезагрузка будет выполнена последовательно."
    )
    
    results = []
    server_list = [s for s in SERVERS if s['id']]
    
    for i, server in enumerate(server_list, 1):
        logger.info(f"Processing server {i}/{len(server_list)}: {server['name']}")
        
        success = await restart_single_vm(server, vm_manager, notifier)
        results.append({'server': server['name'], 'success': success})
        
        # Пауза между перезагрузками (2 минуты)
        if i < len(server_list):
            await notifier.send_pause_notification(
                server_name=server['name'],
                next_server_name=server_list[i]['name'],
                duration=120  # 2 минуты
            )
    
    # Итоговый отчет
    success_count = sum(1 for r in results if r['success'])
    failed_count = len(results) - success_count
    
    summary = f"""📊 **Итог плановой перезагрузки**

✅ Успешно: {success_count}
❌ Ошибок: {failed_count}
📅 Время завершения: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

"""
    
    if failed_count > 0:
        summary += "**Серверы с ошибками:**\n"
        for r in results:
            if not r['success']:
                summary += f"• {r['server']}\n"
    
    await notifier.send_message(summary)

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
            print("  python main.py --server server2         # Restart specific VM")
            print("  python main.py --server server3         # Restart specific VM")
            print("  python main.py --server server4         # Restart specific VM")
    else:
        asyncio.run(restart_all_vms())