# Chatrix Deployment Guide

## Quick Deployment

### 1. Clone and Setup
```bash
git clone https://github.com/yourusername/chatrix.git
cd chatrix

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure
```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your tokens
nano .env
```

### 3. Test Run
```bash
python chatrix.py
```

### 4. Production Deployment

#### Option A: Systemd (Recommended for Raspberry Pi)
```bash
# Copy service file
sudo cp chatrix.service /etc/systemd/system/

# Reload and enable
sudo systemctl daemon-reload
sudo systemctl enable chatrix
sudo systemctl start chatrix

# Check status
sudo systemctl status chatrix
```

#### Option B: Docker
```bash
# Build image
docker build -t chatrix .

# Run container
docker run -d --name chatrix --restart unless-stopped chatrix
```

#### Option C: Screen/Tmux
```bash
# Start in background
screen -S chatrix
source venv/bin/activate
python chatrix.py

# Detach: Ctrl+A, D
# Reattach: screen -r chatrix
```

## Environment Variables

| Variable | Description | Source |
|---|---|---|
| `BOT_TOKEN` | Telegram Bot Token | @BotFather |
| `OPENROUTER_API_KEY` | OpenRouter API Key | openrouter.ai |

## Data Directory Structure

```
data/
|
|--- chat_settings.json  # Chat preferences
|--- likes.json          # Vote data
|--- challenges.json     # Challenge data
|--- chat_history.json   # Message history
```

## Monitoring

### Check Logs
```bash
# Systemd logs
journalctl -u chatrix -f

# Application logs (if configured)
tail -f logs/chatrix.log
```

### Health Check
```bash
# Check if bot is running
systemctl is-active chatrix

# Check resource usage
top -p $(pgrep -f chatrix.py)
```

## Troubleshooting

### Common Issues

1. **Permission Denied**
   ```bash
   sudo chown -R $USER:$USER data/
   ```

2. **Missing Dependencies**
   ```bash
   pip install -r requirements.txt --upgrade
   ```

3. **Token Issues**
   - Verify BOT_TOKEN from @BotFather
   - Check OPENROUTER_API_KEY is valid
   - Ensure .env file is loaded

4. **Memory Issues**
   ```bash
   # Clear chat history if too large
   rm data/chat_history.json
   ```

## Updates

### Update Bot
```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt --upgrade
sudo systemctl restart chatrix
```

### Backup Data
```bash
# Backup data directory
cp -r data/ backup/data_$(date +%Y%m%d)/
```

## Security Notes

- Never commit real tokens to repository
- Use environment variables for secrets
- Regularly rotate API keys
- Monitor bot permissions
- Keep dependencies updated

## Performance Tips

1. **Memory Management**
   - Limit chat history size
   - Regular cleanup of old data
   - Monitor memory usage

2. **API Rate Limits**
   - Configure cooldowns appropriately
   - Use fallback models
   - Implement retry logic

3. **Database Optimization**
   - Consider SQLite for large deployments
   - Implement data archiving
   - Regular maintenance
