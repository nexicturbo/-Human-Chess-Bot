# Human Chess Bot

A chess bot that plays like a human using the **Maia neural network** and **research-based thinking time simulation**. Designed for Chess.com and Lichess.org.

## The Problem with Chess Bots

Traditional chess bots (like Stockfish) are easily detected because:
- They play perfect moves instantly or with fixed delays
- Their timing patterns are inhuman (consistent, predictable)
- Move selection is superhuman (always optimal)

**Result:** Most bots get banned within a few games.

## Our Solution: Human Mode

This bot solves detection in two ways:

### 1. Maia Neural Network for Human-Like Moves

[Maia](https://maiachess.com/) is a neural network trained on millions of human games at specific ELO ratings (1100-1900). Instead of finding the "best" move, Maia predicts **what a human of that rating would actually play** - including the natural mistakes and suboptimal choices humans make.

### 2. Research-Based Thinking Time Simulation

**This is the critical innovation.** Using Maia alone still resulted in bans within 4 games. After implementing research-based thinking times, **we achieved 130+ games without detection.**

Our thinking time model is based on analysis of **12+ million Lichess games** and academic psychology research:

| Research Finding | Implementation |
|-----------------|----------------|
| **21.26% of moves are premoves** | Premove probability system with context awareness |
| **Inverted U-curve timing** | Opening fast → Middlegame slow → Endgame fast |
| **Log-normal distribution** | Heavy-tailed sampling (NOT Gaussian) |
| **Move correlation (AR(1), ρ=0.4)** | Each move's time depends on previous move |
| **ELO-based variability** | SD = a + b × Mean (coefficients vary by rating) |
| **Context-aware adjustments** | Recaptures, forced moves, complexity factors |

```
Think Time Formula:
├── Base time from game phase (inverted U-curve)
├── × Complexity factor (legal moves, captures, checks)
├── × Move type modifier (recaptures, forced moves, castling)
├── × Time control scaling (blitz/rapid)
├── + Move correlation (40% weight from previous move)
└── → Sample from log-normal distribution
```

## Screenshots

### Main Interface
![Main Interface](screenshots/main_ui.png)

### Bot in Action (Chess.com)
![Bot Playing on Chess.com](screenshots/bot_in_action.png)

### 133+ Games Without Detection
![Game History showing 133 games](screenshots/game_history.png)

## Features

### Human Mode (Recommended)
- **Maia ELO Selection**: Choose your simulated rating (1100-1900)
- **Time Control Modes**: Blitz or Rapid timing profiles
- **Realistic Mistakes**: Plays like a human, not a superhuman
- **Natural Timing**: Indistinguishable from human players

### Stockfish Mode (High Detection Risk)
- Traditional Stockfish engine (skill levels 0-20)
- Configurable depth, memory, and CPU threads
- **Warning**: High detection risk on Chess.com

### Other Features
- **Non-Stop Matches**: Automatically queues new games after each match
- **Manual Mode**: Press hotkey to see best move, play it yourself
- **Evaluation Display**: Real-time position evaluation and WDL percentages
- **Accuracy Tracking**: Bot accuracy vs opponent accuracy statistics
- **Move Overlay**: Visual arrow showing suggested moves
- **Modern Dark UI**: Clean PyQt6 interface with card-based layout

## Supported Platforms

| Platform | Human Mode | Stockfish Mode | Non-Stop |
|----------|-----------|----------------|----------|
| Chess.com | Yes | Yes (risky) | Yes |
| Lichess.org | Yes | Yes | Planned |

## Installation

### Prerequisites
- Python 3.8+
- Google Chrome browser
- Windows or Linux

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/nexicturbo/Human-Chess-Bot.git
   cd Human-Chess-Bot
   ```

2. **Create virtual environment**
   ```bash
   # Windows
   python -m venv venv

   # Linux
   python3 -m venv venv
   ```

3. **Install dependencies**
   ```bash
   # Windows
   venv\Scripts\pip.exe install -r requirements.txt

   # Linux
   venv/bin/pip3 install -r requirements.txt
   ```

4. **Maia weights and lc0** (included)

   Everything needed for Human Mode is already included:
   - lc0 engine in `engines/lc0/`
   - Maia weights (1100-1900 ELO) in `maia_original/maia_weights/`

   No additional downloads required for Human Mode.

## Usage

### Starting the Bot

```bash
# Windows
run.bat
# or
venv\Scripts\python.exe src\gui_pyqt.py

# Linux
./run.sh
# or
venv/bin/python3 src/gui_pyqt.py
```

### Quick Start

1. Click **"Auto Download"** to install Stockfish (or **"Select"** to choose existing)
2. Click **"Open Browser"** - Chrome opens to your selected chess site
3. Navigate to a live match
4. **Enable Human Mode** (toggle in settings)
5. Configure Maia ELO and time control
6. Click **"Start"** or press **1**

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| **1** | Start bot |
| **2** | Stop bot |
| **3** | Make move (manual mode only) |

### Human Mode Settings

| Setting | Description |
|---------|-------------|
| **Maia ELO** | Simulated player rating (1100-1900). Higher = stronger but still human-like |
| **Time Control** | Affects thinking times: Blitz (faster) or Rapid (slower, more deliberate) |
| **Use GPU** | Enable for faster inference if you have a compatible GPU |

### Non-Stop Matches

Enable **"Non-Stop Matches"** to automatically:
1. Detect game completion
2. Click "New Game" button
3. Wait for opponent
4. Start playing the next game

Tested for **133+ consecutive games** without manual intervention.

## Technical Details

### Thinking Time Research

The thinking time model implements findings from:
- **Lichess Database Analysis**: 12+ million games analyzed for timing patterns
- **Psychology Research**: Human decision-making under time pressure
- **Premove Studies**: When and why humans premove

Key parameters:
```python
# Premove probability
base_premove_prob = 0.2126  # 21.26% from research

# Move correlation
rho = 0.4  # AR(1) autocorrelation coefficient

# ELO-based variability (SD = a + b * Mean)
# Low ELO:  a=0.1, b=0.91
# High ELO: a=0.6, b=1.36

# Time control scaling
time_scales = {"bullet": 0.4, "blitz": 1.0, "rapid": 2.5}
```

### Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────┐
│   PyQt6 GUI     │────▶│  StockfishBot    │────▶│   Chrome    │
│   (Main Thread) │     │  (Subprocess)    │     │  (Selenium) │
└─────────────────┘     └──────────────────┘     └─────────────┘
                               │
                               ▼
                        ┌──────────────────┐
                        │   Maia Worker    │
                        │  (lc0 + weights) │
                        └──────────────────┘
```

- **GUI Process**: PyQt6 interface, signal handling, settings management
- **Bot Process**: Game state detection, move execution, IPC with GUI
- **Maia Worker**: Subprocess running lc0 with Maia neural network weights

### File Structure

```
├── src/
│   ├── gui_pyqt.py        # Main GUI application
│   ├── stockfish_bot.py   # Bot logic and game loop
│   ├── maia_manager.py    # Maia subprocess management
│   ├── maia_worker.py     # Maia inference + thinking time
│   ├── workers.py         # Background worker threads
│   ├── signals.py         # PyQt signal definitions
│   ├── overlay.py         # Move arrow overlay
│   └── grabbers/
│       ├── chesscom_grabber.py   # Chess.com scraping
│       └── lichess_grabber.py    # Lichess scraping
├── engines/
│   └── lc0/               # Leela Chess Zero engine
├── maia_original/
│   └── maia_weights/      # Maia neural network weights
└── requirements.txt
```

## Results

### Detection Avoidance

| Configuration | Games Before Ban |
|--------------|------------------|
| Stockfish (raw) | ~1-2 games |
| Maia only | ~4 games |
| **Maia + Thinking Times** | **133+ games (no ban)** |

The research-based thinking time simulation is the key differentiator. Without it, even human-like moves get flagged due to timing patterns.

### Accuracy Metrics

In Human Mode, the bot achieves realistic accuracy scores:
- **Bot Accuracy**: Compared against Stockfish's best move
- **Opponent Accuracy**: Tracked for reference
- Both displayed in real-time in the UI

## Disclaimer

This project is for **educational and research purposes only**.

Using this bot to cheat in online games violates the terms of service of Chess.com and Lichess.org. The authors do not condone cheating and are not responsible for any bans or consequences from misuse.

The goal of this project is to explore:
- Human-like AI behavior modeling
- Detection avoidance through behavioral simulation
- Neural network applications in game playing

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

- [Maia Chess](https://maiachess.com/) - Human-like neural network
- [lc0](https://lczero.org/) - Leela Chess Zero engine
- [Stockfish](https://stockfishchess.org/) - Open source chess engine
- [PawnBit](https://github.com/PanagiotisIatrou/PawnBit) - Original project foundation
