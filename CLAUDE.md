# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**SCAIPOT** (Scam AI Honeypot) is a multi-platform, AI-powered honeypot system designed to detect, engage, and analyze cryptocurrency scammers across Signal, Telegram, and WhatsApp. The project combines conversational AI (Claude API), blockchain monitoring, and network analysis to waste scammer time, collect intelligence, and report fraudulent activities.

**Status**: Alpha v0.1.0 - In Active Development (Implementation Phase)
**Tech Stack**: Python 3.10+, Docker, Redis, PostgreSQL, Anthropic Claude API
**License**: MIT

> **Current Phase**: Transitioning from planning to implementation. Core architecture complete, actively generating project structure and implementing bot adapters. See [STATUS.md](STATUS.md) for detailed progress tracking.

## Development Commands

### Installation and Setup
```bash
# Install dependencies (when project files exist)
pip install -e .

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment template
cp .env.example .env
# Then edit .env with your API keys
```

### Testing
```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ -v --cov=src/scaipot --cov-report=html

# Run only unit tests
pytest tests/unit/ -v

# Run only integration tests
pytest tests/integration/ -v

# Run specific test markers
pytest -m unit
pytest -m integration
pytest -m slow
```

### Code Quality
```bash
# Format code with Black
black src/ --line-length 100

# Check code style with Flake8
flake8 src/

# Sort imports
isort src/

# Type checking with mypy
mypy src/

# Run all quality checks
black src/ && isort src/ && flake8 src/ && mypy src/
```

### Docker Operations
```bash
# Start full stack
docker-compose up -d

# View logs
docker-compose logs -f scaipot

# Stop all services
docker-compose down

# Rebuild containers
docker-compose build

# Start only specific services
docker-compose up -d postgres redis
```

### Running the Application
```bash
# Initialize configuration
python -m scaipot.cli init

# Create a honeypot
python -m scaipot.cli create-honeypot \
  --platform telegram \
  --category bitcoin_investment \
  --name "BTCNewbie"

# Start honeypot
python -m scaipot.honeypot --config honeypots/btc_newbie.yaml

# CLI entry point
scaipot --help
```

## Architecture

### Core Components

1. **Bot Adapters** (`src/scaipot/bots/`)
   - Platform-agnostic bot interface (`base.py`)
   - Platform-specific implementations: `telegram_bot.py`, `signal_bot.py`, `whatsapp_bot.py`
   - Each adapter handles message I/O for its respective platform

2. **LLM Engine** (`src/scaipot/llm_engine/`)
   - `claude_client.py`: Wrapper for Anthropic Claude API
   - `prompt_cache.py`: Redis-based caching for 90% cost reduction
   - `response_generator.py`: Orchestrates AI responses based on category personas
   - Uses prompt caching to reuse system prompts and reduce API costs

3. **MCP Integration** (`src/scaipot/mcp_integration/`)
   - `mcp_client.py`: Client for MCP-Prompts server
   - `category_loader.py`: Loads and manages 12 scam category templates
   - Enables dynamic prompt updates without restarting honeypots

4. **Behaviors** (`src/scaipot/behaviors/`)
   - `url_clicker.py`: Simulates clicking on scammer links with screenshot capture
   - `vm_manager.py`: Spawns disposable Windows/Linux VMs with RDP/SSH access
   - `blockchain_monitor.py`: Tracks wallet addresses and dust attacks
   - `network_analyzer.py`: tcpdump and MITM proxy for traffic analysis

5. **Fraud Detection** (`src/scaipot/fraud_detection/`)
   - `pattern_detector.py`: NLP-based detection of scam indicators
   - `indicators.py`: Extracts BTC addresses, IBANs, URLs, phone numbers
   - `ml_classifier.py`: ML model for scam type classification

6. **Reporting** (`src/scaipot/reporting/`)
   - `alerts.py`: Real-time Slack/Discord notifications for admins
   - `bitcoin_whoswho.py`: Auto-reporting to Bitcoin Who's Who database
   - `admin_dashboard.py`: Web UI for monitoring honeypot activity

7. **Storage** (`src/scaipot/storage/`)
   - `db.py`: PostgreSQL models for conversations, patterns, alerts
   - `redis_store.py`: Redis operations for caching and session management
   - `logger.py`: Structured logging of all scammer interactions

### Data Flow

1. Scammer sends message → Platform bot receives
2. Bot adapter normalizes message → Passes to LLM engine
3. LLM engine fetches category prompt from MCP → Checks cache
4. Claude generates response with cached system prompt → 90% cost savings
5. Response sent back through bot adapter → Logged to PostgreSQL
6. Fraud detection analyzes message → Extracts indicators (BTC, URLs)
7. If high-risk pattern detected → Admin alert triggered
8. Behaviors execute (URL click, blockchain tracking) → Intelligence collected

### Configuration System

- **YAML-based categories**: 12 pre-defined scam honeypot templates in `config/honeypot_categories/`
  - Each category defines: persona, backstory, conversation style, risk tolerance
  - Examples: `bitcoin_investment.yaml`, `romance_scam.yaml`, `tech_support.yaml`

- **Environment configuration**: `.env.example` template for API keys and service URLs
  - Anthropic API key (required)
  - Platform tokens: Telegram, Signal, WhatsApp
  - Redis and PostgreSQL connection strings
  - MCP-Prompts server URL
  - Admin webhook URLs for alerts

- **Docker orchestration**: `docker-compose.yml` defines full stack
  - PostgreSQL for persistence
  - Redis for caching
  - MCP-Prompts server
  - SCAIPOT main application
  - Grafana for monitoring
  - mitmproxy for network analysis

## Important Patterns

### Prompt Caching Strategy
- System prompts (category personas) are cached in Redis with 24h TTL
- Only user messages change between requests → massive cost savings
- Cache key format: `scaipot:prompt:category:{category_name}:v{version}`
- Invalidate cache when category definitions update in MCP

### Async Operations
- All bot adapters use async/await for non-blocking I/O
- FastAPI for async REST endpoints
- Redis async client for caching
- PostgreSQL async operations via SQLAlchemy 2.0

### Testing Philosophy
- Unit tests: Mock external services (Claude API, platform bots, Redis)
- Integration tests: Use real Redis/PostgreSQL in Docker containers
- Fixtures in `tests/conftest.py` for common test data
- Always test both success and error paths

### Security Considerations
- **Never** commit API keys or tokens to Git
- Use `.env` files for secrets (excluded in `.gitignore`)
- Honeypot VMs are isolated and disposable
- All scammer interactions logged for forensic analysis
- MITM proxy only operates on honeypot traffic, not production

## Project Structure Notes

### Key Directories
- `src/scaipot/`: Main Python package with all application code
- `config/honeypot_categories/`: 12 YAML templates for scam categories
- `tests/`: Unit tests (7 files) and integration tests (4 files)
- `docker/`: Dockerfiles and VM honeypot configurations
- `docs/`: Dual-language documentation (English + Czech)
- `scripts/`: Deployment and utility shell scripts

### Current State (Alpha v0.1.0 - In Development)

**Completed**:
- ✅ Repository reorganization (docs/, scripts/, templates/)
- ✅ Professional README.md with status badges
- ✅ Comprehensive planning documentation
- ✅ CLAUDE.md (this file) for AI assistant guidance
- ✅ STATUS.md for progress tracking
- ✅ Integration architecture with MCP-Prompts defined

**In Progress**:
- 🚧 Project structure generation from templates (scripts/script.py)
- 🚧 Docker Compose configuration with full stack
- 🚧 MCP-Prompts honeypot endpoint implementation

**Next Steps**:
1. Execute `scripts/script.py` to generate `src/scaipot/` directory structure
2. Create `docker-compose.yml` with PostgreSQL, Redis, mcp-prompts, scaipot
3. Implement honeypot endpoints in mcp-prompts repository
4. Create basic bot adapters (Telegram first, then Signal)
5. Implement LLM engine with Claude API + prompt caching
6. Add fraud detection and pattern matching
7. Set up testing infrastructure and CI/CD

See [STATUS.md](STATUS.md) for detailed milestone tracking and timeline.

## Common Tasks

### Adding a New Scam Category
1. Create YAML file in `config/honeypot_categories/`
2. Define persona, backstory, conversation_style, risk_tolerance
3. Upload to MCP-Prompts server (auto-sync via volume mount in Docker)
4. Category becomes available without restart

### Adding a New Platform Bot
1. Create new file in `src/scaipot/bots/` (e.g., `discord_bot.py`)
2. Inherit from `base.py` abstract class
3. Implement: `send_message()`, `receive_message()`, `handle_media()`
4. Add platform credentials to `.env.example`
5. Register bot adapter in `main.py`

### Debugging Conversation Flow
1. Enable DEBUG logging in `.env`: `LOG_LEVEL=DEBUG`
2. Check logs: `docker-compose logs -f scaipot`
3. Inspect PostgreSQL conversations table
4. Review Redis cache keys: `redis-cli KEYS "scaipot:*"`
5. Check Claude API usage in Anthropic Console

### Running Single Test
```bash
# Test specific module
pytest tests/unit/test_llm_engine.py -v

# Test specific function
pytest tests/unit/test_pattern_detector.py::test_bitcoin_address_extraction -v

# Test with print output
pytest tests/unit/test_mcp_integration.py -v -s
```

## Package Dependencies

From `pyproject.toml`:

**Core Dependencies**:
- `anthropic>=0.26.0` - Claude API client
- `python-telegram-bot>=20.0` - Telegram bot framework
- `signalbot>=0.6.0` - Signal bot framework
- `whatsapp-business-python>=1.0.0` - WhatsApp Business API
- `redis>=5.0.0` - Caching and session storage
- `sqlalchemy>=2.0.0` - PostgreSQL ORM
- `pydantic>=2.0.0` - Data validation
- `docker>=6.0.0` - VM honeypot orchestration

**Dev Dependencies**:
- `pytest>=7.4.0` with `pytest-asyncio`, `pytest-cov`, `pytest-mock`
- `black>=23.0.0` - Code formatting (line-length=100)
- `flake8>=6.0.0` - Linting
- `mypy>=1.5.0` - Type checking

**Coding Standards**:
- Black formatting: 100 character line length
- Type hints required (mypy strict mode)
- Async/await for all I/O operations
- Structured logging with `structlog`

## Notes for AI Assistants

- This is a **security research project** focused on **defensive** honeypot operations
- Scammers initiate contact; honeypots are passive
- Always maintain ethical boundaries: no "hacking back", no DDoS, no public doxxing
- When implementing behaviors, ensure proper sandboxing and isolation
- Cost optimization via prompt caching is critical - don't bypass it
- Test thoroughly before deploying - scammers will probe for weaknesses
- Document all intelligence collection methods for legal/ethical transparency
