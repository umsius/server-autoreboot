# VPS Management Bot for Yandex Cloud

Бот для автоматической перезагрузки виртуальных машин в Yandex Cloud через Telegram с обновлением статуса в одном сообщении.

## 📋 Требования

- Внешний VPS (Ubuntu/Debian) с выходом в интернет
- Сервисная учетная запись в Yandex Cloud с ролью `compute.editor`
- Виртуальные машины в Yandex Cloud (их Instance ID)
- Telegram Bot Token (получить у @BotFather)
- Telegram Chat ID администраторов

## 🚀 Полная инструкция по установке

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
Подключитесь к вашему VPS (например 1.1.1.1)
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

