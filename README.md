# Chatrix — Telegram бот

Telegram-бот с AI-генерацией контента и интерактивными функциями.

## Установка

```bash
cd /DATA/Bot_chatrix
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Настрой токены в `.env` (см. `.env.example`).

**Автозапуск:**
```bash
sudo cp chatrix.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable chatrix
sudo systemctl start chatrix
journalctl -u chatrix -f
```

## Команды

### Основные
| Команда | Описание |
|---|---|
| `/draw [описание]` | Нарисовать картинку |
| `/redraw [уточнение]` | Перерисовать /draw с улучшением |
| `/ask [вопрос]` | Прямой вопрос AI |
| `/search [запрос]` | Поиск в интернете + сводка |
| `/wiki [тема]` | Википедия + сводка |
| `/agent [задача]` | Многошаговый AI-ответ |
| `/vision, анализ` | Анализ фото или текста |
| `/tts [текст]` | Озвучить текст |

### Настройки
| Команда | Описание |
|---|---|
| `/set style [описание]` | Стиль общения бота |
| `/set group [N]` | Частота ответов (по умолч. 10) |
| `/set chance [0-1]` | Шанс стикеров |
| `/set mode [default/mystyle]` | Режим стиля |
| `/status` | Статус бота и чата |

### Развлечения
| `/rate`, `/roast`, `/fortune`, `/ship`, `/advice`, `/who` |
|---|

### Утилиты
| `/plan [цель]` | Пошаговый план |
|---|---|
| `/task [текст]` | Добавить задачу |
| `/tasks` | Список задач |

### Админ
| `/models` | Сменить модель AI |
|---|---|
| `/backup` | Создать бэкап |

## Структура

```
chatrix/
├── chatrix.py          # Точка входа
├── config.py           # Конфигурация
├── requirements.txt
├── chatrix.service     # Systemd-юнит
├── .env.example
├── handlers/
│   ├── misc.py         # AI-ответы, авто-декодинг
│   ├── native_features.py  # /draw, /redraw, /ask, /vision, /tts и др.
│   ├── generate.py     # S-команды (мемы, демотиваторы)
│   ├── settings.py     # Настройки чата
│   ├── inline.py       # Инлайн-режим
│   ├── mafia.py        # Игра мафия
│   └── business.py     # Business-подключения
├── utils/
│   ├── ai.py           # Gen AI, промпты, BOT_KNOWLEDGE
│   ├── ai_config.py    # Очистка ответов, цепочки моделей
│   ├── native_features.py  # Генерация изображений, поиск
│   ├── history.py      # Управление историей
│   ├── intents.py      # Определение намерений (web_search)
│   ├── chat_style.py   # Стили общения (/set)
│   └── ...             # reactions, demotivator, meme_gen и др.
└── data/
    ├── system_prompts.json
    ├── chat_settings.json
    └── ...
```
