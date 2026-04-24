# VPS Management Bot for Yandex Cloud

Бот для автоматической перезагрузки виртуальных машин в Yandex Cloud через Telegram с обновлением статуса в одном сообщении.

## Требования

- Внешний VPS (Ubuntu/Debian) с выходом в интернет
- Сервисная учетная запись в Yandex Cloud с ролью `compute.editor`
- Виртуальные машины в Yandex Cloud (их Instance ID)
- Telegram Bot Token (получить у @BotFather)
- Telegram Chat ID администраторов

##  Полная инструкция по установке

### Подготовка Yandex Cloud

```bash
# Установка Yandex Cloud CLI
curl https://storage.yandexcloud.net/yandexcloud-yc/install.sh | bash
source ~/.bashrc

# Авторизация (перейдите по ссылке, скопируйте OAuth токен)
yc init

# Создание сервисного аккаунта
yc iam service-account create --name vm-manager-bot

# Получение ID каталога и сервисного аккаунта
yc resource-manager folder list
yc iam service-account list

# Назначение роли compute.editor (замените <folder-id> и <service-account-id>)
yc resource-manager folder add-access-binding <folder-id> \
  --role compute.editor \
  --subject serviceAccount:<service-account-id>

# Создание авторизованного ключа (выберите RSA_2048)
yc iam key create --service-account-name vm-manager-bot --output key.json

# Получение Instance ID ваших ВМ
yc compute instance list
```
# Настройка внешнего VPS
Подключитесь к вашему VPS
```ssh root@<ip-вашего-vps>```

Создание директории проекта
```
mkdir -p /opt/vm-restart-bot
cd /opt/vm-restart-bot
```
Скопируйте файл key.json с вашей локальной машины на VPS (выполните на локальной машине)
```scp key.json root@<ip-вашего-vps>:/opt/vm-restart-bot/```

### На VPS установите правильные права на ключ
```chmod 600 key.json```

# Установка зависимостей Python
```pip3 install -r requirements.txt```

# Создание .env файла (замените значения на свои)
```cat > .env << 'EOF'
# Telegram Bot Configuration
BOT_TOKEN="token"
ADMIN_IDS="123456789,123456789"
```
# Yandex Cloud Default Configuration
```
YC_FOLDER_ID=""

# Сервер 1
SERVER1_INSTANCE_ID=""
SERVER1_NAME="Server-01"
SERVER1_IP=""
SERVER1_KEY_FILE=""
SERVER1_FOLDER_ID=""

# Сервер 2
SERVER2_INSTANCE_ID=""
SERVER2_NAME="Server-02"
SERVER2_IP=""
SERVER2_KEY_FILE=""
SERVER2_FOLDER_ID=""

# Сервер 3 (если есть)
SERVER3_INSTANCE_ID=""
SERVER3_NAME="Server-03"
SERVER3_IP=""
SERVER3_KEY_FILE=""
SERVER3_FOLDER_ID=""

# Сервер 4 (если есть)
SERVER4_INSTANCE_ID=""
SERVER4_NAME="Server-04"
SERVER4_IP=""
SERVER4_KEY_FILE=""
SERVER4_FOLDER_ID=""
EOF
```
# Создание requirements.txt
```
cat > requirements.txt << 'EOF'
python-telegram-bot==20.7
yandexcloud==0.285.0
python-dotenv==1.0.0
EOF
```
# Установка зависимостей
```pip3 install -r requirements.txt```

# Создание файлов vm_manager.py и main.py (скопируйте содержимое из репозитория)

# Проверка работы
```python3 main.py --server server1```

# Настройка автоматической перезагрузки по расписанию (ежедневно в 8:55)
crontab -e

# Добавьте строку:
```55 8 * * * cd /opt/vm-restart-bot && /usr/bin/python3 main.py --all >> /var/log/vm_restart.log 2>&1```

# Просмотр логов
```tail -f /var/log/vm_restart.log```

# Ручная перезагрузка всех серверов
```python3 main.py --all```

# Ручная перезагрузка конкретного сервера
```
python3 main.py --server server1
python3 main.py --server server2
python3 main.py --server server3
python3 main.py --server server4
```

# Проверка статуса серверов через CLI
```yc compute instance list --folder-id ID```

# Для работы с несколькими аккаунтами используйте разные профили
```
yc config profile create account-b
yc config set service-account-key key2.json
yc config set folder-id ID
```

# Просмотр активных профилей
```yc config profile list```

# Переключение между профилями
```
yc config profile activate default
yc config profile activate account-b
```
