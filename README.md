# Chatrix - Telegram Bot

Telegram-bot with AI-powered content generation and interactive features. Optimized for Raspberry Pi 4.

## Features

- **AI Content Generation**: Text, memes, demotivators, jokes, polls
- **Interactive Games**: Chat-based quizzes and challenges  
- **Social Features**: Voting, statistics, leaderboards
- **Smart Learning**: AI learns from chat preferences
- **Multi-language**: Russian interface with English AI support

## Installation

### 1. Clone the repository
```bash
git clone https://github.com/yourusername/chatrix.git
cd chatrix
```

### 2. Set up virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure tokens in `config.py`
```python
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"          # from @BotFather
OPENROUTER_API_KEY = "YOUR_API_KEY_HERE"  # from OpenRouter
```

### 4. Test manually
```bash
source venv/bin/activate
python chatrix.py
```

### 5. Auto-start with systemd
```bash
sudo cp chatrix.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable chatrix
sudo systemctl start chatrix
sudo systemctl status chatrix
```

View logs:
```bash
journalctl -u chatrix -f
```

---

## Commands

### Content Generation
| Command | Description |
|---|---|
| `S g` | Generation panel |
| `S g <text>` | Generate text with start |
| `S g <1-250>` | Text of specified length |
| `S g l` | Long text |
| `S g w` | Random word |
| `S g w <1-50>` | Word of specified length |
| `S g p` | Poll based on chat |
| `S g m` | Random meme |
| `S g d` | Demotivator (reply to photo) |
| `S g d ai` | AI-powered demotivator |
| `S g a` | Joke based on chat |
| `S g a <start>` | Joke with start |
| `S g r` | Random phrase from chat |

### Interactive Features
| Command | Description |
|---|---|
| `S top` | Best demotivators rating |
| `S stats` | Your voting statistics |
| `S game quiz` | Chat trivia game |
| `S challenge create <theme>` | Create challenge |
| `S challenge` | Active challenge info |

### Admin Commands
| Command | Description |
|---|---|
| `S c` | Chat settings (admin only) |
| `S h` | Help |

---

## Project Structure

```
chatrix/
|
|--- chatrix.py              # Main bot file
|--- config.py               # Configuration
|--- requirements.txt        # Dependencies
|--- chatrix.service         # Systemd service
|--- .gitignore              # Git ignore rules
|--- README.md               # This file
|
|--- handlers/               # Command handlers
|   |--- generate.py         # Content generation
|   |--- settings.py         # Admin settings
|   |--- and misc.py         # Misc commands & games
|
|--- utils/                  # Utilities
|   |--- ai.py               # AI integration
|   |--- access.py           # Permission checks
|   |--- cooldown.py         # Rate limiting
|   |--- demotivator.py      # Demotivator creation
|   |--- history.py          # Chat history
|   |--- likes.py            # Voting system
|   |--- user_stats.py       # User statistics
|   |--- quiz.py             # Quiz game
|   |--- challenges.py       # Challenge system
|   |--- and settings_store.py
|
|--- data/                   # Data storage
|   |--- chat_settings.json  # Chat preferences
|   |--- likes.json          # Vote data
|   |--- challenges.json     # Challenge data
|   |--- chat_history.json   # Message history
|
|--- venv/                   # Virtual environment
```

---

## API Configuration

The bot uses **OpenRouter** for AI models with fallback support:

- **Primary Model**: `openai/gpt-oss-120b:free`
- **Fallback Models**: `meta-llama/llama-3.2-3b-instruct:free`, `minimax/minimax-m2.5:free`

---

## Features Details

### Smart Demotivators
- AI analyzes chat history and context
- Learns from user preferences via voting
- Few-shot learning from top-rated examples

### Interactive Challenges
- User-created competitions
- 24-hour duration
- Voting system for winners
- Leaderboard tracking

### Chat Quiz
- Questions based on real chat history
- Multiple question types
- Automatic answer checking

### Statistics & Analytics
- Personal voting patterns
- Top-rated content discovery
- Chat activity insights

---

## Development

### Adding New Commands
1. Create handler in `handlers/`
2. Add utilities in `utils/`
3. Import and register in `chatrix.py`
4. Update help text in `misc.py`

### Data Storage
All data stored in JSON format under `data/` directory:
- Chat history with automatic cleanup
- User preferences and settings
- Voting records and statistics
- Challenge data and results

---

## Contributing

1. Fork the repository
2. Create feature branch
3. Make your changes
4. Test thoroughly
5. Submit pull request

---

## License

This project is open source and available under the MIT License.
