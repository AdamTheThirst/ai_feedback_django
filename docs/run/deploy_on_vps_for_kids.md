# Деплой Django-проекта на VPS — очень простой гайд (для новичка)

> Этот гайд написан максимально простыми словами.
> Представь, что VPS — это «удалённый компьютер в интернете»,
> а ты на нём запускаешь свой сайт.

---

## 0. Что тебе нужно заранее

1. **VPS** с Linux (обычно Ubuntu 22.04/24.04).
2. **IP-адрес** VPS (например `123.45.67.89`).
3. **Пароль или SSH-ключ** для входа на VPS.
4. Домен (не обязательно, но удобно).

---

## 1. Как зайти на VPS

На своём компьютере открой терминал и выполни:

```bash
ssh root@ТВОЙ_IP
```

Пример:

```bash
ssh root@123.45.67.89
```

Если попросит подтвердить подключение — напиши `yes`.

---

## 2. Подготовка сервера

Обнови пакеты:

```bash
apt update && apt upgrade -y
```

Установи нужные программы:

```bash
apt install -y python3 python3-venv python3-pip git nginx
```

---

## 3. Скопируй проект на VPS

Перейди в папку `/opt` и клонируй репозиторий:

```bash
cd /opt
git clone <URL_ТВОЕГО_РЕПО> ai_feedback_django
cd ai_feedback_django
```

---

## 4. Создай виртуальное окружение и установи зависимости

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements/base.txt
```

---

## 5. Создай `.env`

Создай файл:

```bash
nano .env
```

Минимальный пример:

```env
DJANGO_SETTINGS_MODULE=config.settings.production
SECRET_KEY=СЮДА_ДЛИННЫЙ_СЕКРЕТ
ALLOWED_HOSTS=ТВОЙ_IP,ТВОЙ_ДОМЕН
LLM_BASE_URL=http://127.0.0.1:8000/v1
LLM_API_KEY=dummy
LLM_MODEL_NAME=Qwen/Qwen3-32B
```

Сохрани файл: `Ctrl+O`, Enter, `Ctrl+X`.

---

## 6. Подготовь базу и статику

```bash
source .venv/bin/activate
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

---

## 7. Проверь, что проект вообще запускается

```bash
source .venv/bin/activate
python manage.py runserver 0.0.0.0:8000
```

Открой в браузере:

- `http://ТВОЙ_IP:8000`

Если всё видно — отлично.
Останови сервер: `Ctrl+C`.

---

## 8. Поставь Gunicorn (чтобы сайт работал как сервис)

Установи gunicorn:

```bash
source .venv/bin/activate
pip install gunicorn
```

Проверь запуск:

```bash
gunicorn config.wsgi:application --bind 127.0.0.1:8000
```

Если запустилось — `Ctrl+C`.

---

## 9. Создай systemd-сервис

Создай файл:

```bash
nano /etc/systemd/system/ai_feedback_django.service
```

Вставь:

```ini
[Unit]
Description=ai_feedback_django gunicorn
After=network.target

[Service]
User=root
WorkingDirectory=/opt/ai_feedback_django
Environment="DJANGO_SETTINGS_MODULE=config.settings.production"
ExecStart=/opt/ai_feedback_django/.venv/bin/gunicorn config.wsgi:application --bind 127.0.0.1:8000
Restart=always

[Install]
WantedBy=multi-user.target
```

Сохрани и выполни:

```bash
systemctl daemon-reload
systemctl enable ai_feedback_django
systemctl start ai_feedback_django
systemctl status ai_feedback_django
```

---

## 10. Настрой Nginx

Создай конфиг:

```bash
nano /etc/nginx/sites-available/ai_feedback_django
```

Вставь:

```nginx
server {
    listen 80;
    server_name _;

    location /static/ {
        alias /opt/ai_feedback_django/staticfiles/;
    }

    location /media/ {
        alias /opt/ai_feedback_django/media/;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Включи сайт и перезапусти nginx:

```bash
ln -s /etc/nginx/sites-available/ai_feedback_django /etc/nginx/sites-enabled/ai_feedback_django
nginx -t
systemctl restart nginx
```

Теперь сайт должен открываться по `http://ТВОЙ_IP`.

---

## 11. Как обновлять проект после изменений

```bash
cd /opt/ai_feedback_django
git pull
source .venv/bin/activate
pip install -r requirements/base.txt
python manage.py migrate
python manage.py collectstatic --noinput
systemctl restart ai_feedback_django
systemctl restart nginx
```

---

## 12. Если что-то не работает

Проверь логи Django-сервиса:

```bash
journalctl -u ai_feedback_django -n 200 --no-pager
```

Проверь логи Nginx:

```bash
tail -n 200 /var/log/nginx/error.log
```

---

## 13. Очень важная безопасность (обязательно)

1. Создай не-root пользователя.
2. Отключи вход по паролю (оставь SSH-ключ).
3. Настрой firewall (`ufw`).
4. Поставь HTTPS (Let’s Encrypt + certbot).

---

## Коротко: что ты сделал

Ты:
- взял удалённый сервер,
- поставил Python + Nginx,
- запустил Django через Gunicorn,
- проксировал трафик через Nginx,
- и получил рабочий сайт в интернете 🎉
