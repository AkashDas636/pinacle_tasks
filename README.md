# 🎯 Pinacle Suite - Premium Python Applications Collection

A comprehensive collection of 8 feature-rich Python applications with modern web interfaces and original CLI modes. All applications are built with glassmorphic design, dark themes, and responsive layouts.

## 📦 Projects Overview

| # | Project | Port | Type | Description |
|---|---------|------|------|-------------|
| 1 | 🧮 **Calculator** | 5002 | Web | Advanced calculator with neumorphic design |
| 2 | ⏰ **Alarm Clock** | 5003 | Web + GUI | Glassmorphic alarm with Tkinter fallback |
| 3 | 📝 **Quiz Platform** | 5004 | Web + CLI | Interactive quizzes with leaderboard |
| 4 | 💬 **Chat App** | 5005 | Web + Socket | Real-time messaging (Discord-style) |
| 5 | 📚 **Blog** | 5000 | Web | Personal blog with markdown support |
| 6 | 🛒 **E-Commerce** | 5006 | Web + CLI | Product storefront with shopping cart |
| 7 | 🌦️ **Weather** | 5007 | Web + CLI | Live weather dashboard with forecast |
| 8 | 📅 **Calendar** | 8080 | Web | Unified control panel for all apps |

## 🚀 Quick Start

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Pinacle
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Launch an application**
   ```bash
   # Web UI (default)
   python basic_calculator.py         # Port 5002
   
   # Or any other project
   python alarm_clock.py              # Port 5003
   python quiz_platform.py            # Port 5004
   python 2_chat_app.py               # Port 5005
   python blog_site.py                # Port 5000
   python Ecommerce/ecommerce_display.py  # Port 5006
   python "Waether app/weather_app.py"    # Port 5007
   python calendar_reminder.py        # Port 8080
   ```

4. **Open in browser**
   - Applications automatically open in your default browser
   - Or manually visit `http://localhost:<PORT>`

## 🎨 Design Features

All applications include:

- **Glassmorphic UI** - Frosted glass effect with transparency
- **Dark Theme** - Professional dark mode (#0d1117 background)
- **Responsive Design** - Works on mobile, tablet, and desktop
- **Smooth Animations** - Micro-interactions and transitions
- **Consistent Palette**:
  - Primary: `#58a6ff` (GitHub Blue)
  - Success: `#3fb950` (Green)
  - Warning: `#d29922` (Yellow)
  - Error: `#f85149` (Red)

## 💻 Original CLI Modes

Some applications preserve their original interfaces via command flags:

```bash
# Alarm Clock - Tkinter GUI
python alarm_clock.py --gui

# Quiz Platform - Terminal CLI
python quiz_platform.py --cli

# Chat App - Socket mode
python 2_chat_app.py --server
python 2_chat_app.py --client
python 2_chat_app.py --demo

# E-Commerce - Rich terminal UI
python Ecommerce/ecommerce_display.py --cli

# Weather - Terminal interface
python "Waether app/weather_app.py" --cli
```

## 📁 Project Structure

```
Pinacle/
├── 2_chat_app.py              # Real-time chat application
├── alarm_clock.py             # Alarm clock with web UI
├── basic_calculator.py        # Advanced calculator
├── blog_site.py               # Blog engine
├── calendar_reminder.py       # Unified dashboard
├── quiz_platform.py           # Quiz platform
├── requirements.txt           # Python dependencies
├── .gitignore                 # Git ignore file
├── README.md                  # This file
├── Ecommerce/                 # E-commerce module
│   ├── ecommerce_display.py   # Storefront UI
│   ├── products.py            # Product catalog
│   ├── cart.py                # Shopping cart logic
│   └── payment.py             # Payment processing
├── Waether app/               # Weather module
│   ├── weather_app.py         # Weather web UI
│   ├── weather_config.py      # API configuration
│   ├── weather_fetcher.py     # Data fetching
│   └── weather_display.py     # Terminal display
└── templates/                 # HTML templates
    └── index.html             # Legacy template
```

## 🔧 Requirements

- **Python**: 3.8+
- **Flask**: Web framework
- **Requests**: HTTP library for APIs
- **Rich**: Beautiful terminal output
- **SQLite3**: Database (built-in with Python)

See `requirements.txt` for full dependencies list.

## 📊 Features by Application

### 🧮 Calculator
- Basic arithmetic operations
- Advanced functions (trigonometry, power, root)
- Calculation history
- Memory registers
- Neumorphic UI design

### ⏰ Alarm Clock
- Multiple alarm management
- Snooze functionality (5-minute intervals)
- Repeat alarm support
- Browser notifications
- Database persistence

### 📝 Quiz Platform
- Create custom quizzes
- Timed quiz modes
- Real-time scoring
- Leaderboard rankings
- Question categorization

### 💬 Chat Application
- Real-time messaging
- Discord-style interface
- User profiles & avatars
- Channel-based chat rooms
- Socket server/client support

### 📚 Blog Engine
- Create/edit/delete posts
- Tag-based organization
- Full-text search
- Admin panel (password: `admin123`)
- Markdown rendering

### 🛒 E-Commerce
- Product catalog with filtering
- Search functionality
- Shopping cart management
- Coupon/discount codes
- Payment simulator
- Stock management

### 🌦️ Weather Dashboard
- Current weather display
- 7-day forecast
- Location detection (IP-based)
- Unit conversion (°C/°F)
- Interactive weather maps

### 📅 Calendar Dashboard
- Unified control panel
- Event scheduling
- Real-time notifications
- 5 premium color themes
- Database backups & migrations

## 🗄️ Database

Each application uses SQLite for data persistence:
- **auto-created** on first run
- **located** in the application root directory
- **backup** functionality included

Databases are `.gitignore`'d and will be created automatically.

## 🌐 API & Backend

### Flask Routes (Example - Calculator)
- `GET /` - Main interface
- `POST /api/calculate` - Calculate expression
- `GET /api/history` - Retrieve calculation history

### Common Patterns
- JSON API responses
- Session-based state management
- SQLite persistence layer
- Error handling with try-catch

## 🔐 Security Notes

Before production deployment:

1. **Change secret keys** in Flask applications
2. **Update admin credentials** (currently: `admin123`)
3. **Enable HTTPS** on production servers
4. **Sanitize user inputs** - SQL injection prevention
5. **Rate limiting** for APIs
6. **CORS configuration** if needed

## 🚢 Deployment

### Local Development
```bash
python <app-name>.py
```

### Docker Support (Optional)
Create a `Dockerfile`:
```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 5000 5002 5003 5004 5005 5006 5007 8080
CMD ["python", "calendar_reminder.py"]
```

### Environment Variables
Create `.env` file for sensitive data:
```
FLASK_ENV=production
WEATHER_API_KEY=your_key_here
DB_PATH=/data/
```

## 📝 License

This project is open-source and available for educational and commercial use.

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For issues or questions:
- Check the application's built-in help
- Review the source code comments
- Create an issue in the repository

## 🎯 Roadmap

- [ ] Mobile app versions (React Native)
- [ ] Dark/Light theme toggle UI
- [ ] Multi-language support
- [ ] Advanced analytics dashboard
- [ ] Backup/restore utilities
- [ ] Docker Compose setup
- [ ] API documentation (Swagger)
- [ ] Unit tests & CI/CD

## ✨ Credits

Built with modern Python web technologies:
- Flask for web framework
- SQLite for database
- Rich for terminal UI
- Requests for HTTP
- HTML5/CSS3/JavaScript for frontend

---

**Happy coding! 🚀**

Last Updated: 2026-05-27  
Version: 1.0.0
