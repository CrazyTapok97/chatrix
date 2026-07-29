# Chatrix — Telegram бот

Telegram бот с генерацией контента через Google Gemini AI. Работает на Raspberry Pi 4.

## Установка

### 1. Скопируй файлы на малинку
```bash
scp -r chatrix/ root@<IP_МАЛИНКИ>:/DATA/Bot_chatrix
```

### 2. Создай виртуальное окружение и установи зависимости
```bash
cd /DATA/Bot_chatrix
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Настрой токены в config.py
```python
BOT_TOKEN = "1234567890:ABC..."   # от @BotFather
GEMINI_API_KEY = "AIza..."        # от aistudio.google.com
```

### 4. Проверь запуск вручную
```bash
source venv/bin/activate
python chatrix.py
```

### 5. Автозапуск через systemd
```bash
sudo cp chatrix.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable chatrix
sudo systemctl start chatrix
sudo systemctl status chatrix
```

Логи:
```bash
journalctl -u chatrix -f
```

---

## Команды

| Команда | Описание |
|---|---|
| `S g` | Панель генерации |
| `S g <начало>` | Текст с заданным началом |
| `S g <1-250>` | Текст заданной длины |
| `S g l` | Длинный текст |
| `S g w` | Случайное слово |
| `S g w <1-50>` | Слово заданной длины |
| `S g p` | Опрос или викторина |
| `S g m` | Случайный мем |
| `S g d` | Демотиватор (реплай на фото = с картинкой) |
| `S g a` | Анекдот |
| `S g a <начало>` | Анекдот с заданным началом |
| `S c` | Настройки чата (только для админов) |
| `S h` | Помощь |

⏳ Кулдаун: 20 сек для всех, 5 сек для администраторов.
Без кулдауна: `S g w` (генерация слова).

---

## Структура файлов

```
/DATA/Bot_chatrix/
├── chatrix.py
├── config.py
├── requirements.txt
├── chatrix.service
├── venv/
├── data/
│   └── chat_settings.json
├── handlers/
│   ├── generate.py
│   ├── settings.py
│   └── misc.py
└── utils/
    ├── ai.py
    ├── access.py
    ├── cooldown.py
    ├── demotivator.py
    └── settings_store.py
```
