# AI Automation Agent

A comprehensive AI-powered automation agent that uses OpenAI's function calling to integrate with multiple APIs including Slack, Jira, AWS S3, and GitHub. Features OAuth2 authentication, CLI interface, webhook support, and PostgreSQL logging with rollback capabilities.

## 🚀 Features

- **Multi-LLM Support**: Works with OpenAI, DeepSeek, Qwen, Groq, Ollama, and more open source models
- **Cost-Effective**: Use budget-friendly alternatives to GPT-4 or run completely free with local models
- **Multi-Service Integration**: Slack, Jira, AWS S3, GitHub with OAuth2 authentication
- **CLI Interface**: Beautiful command-line interface using Typer with rich output
- **FastAPI Server**: Webhook endpoints for real-time automation triggers
- **PostgreSQL Logging**: Complete audit trail with rollback capability
- **Production Ready**: Structured logging, error handling, and security best practices

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   CLI Interface │    │  FastAPI Server │    │  OpenAI GPT-4   │
│    (Typer)      │    │   (Webhooks)    │    │ Function Calling │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         └───────────────────────┼───────────────────────┘
                                 │
                 ┌─────────────────────────────┐
                 │    Core Agent Engine        │
                 │  - Command Processing       │
                 │  - Function Execution       │
                 │  - Rollback Management      │
                 └─────────────────────────────┘
                                 │
    ┌────────────────────────────┼─────────────┐
    │                            │             │
┌───▼────┐  ┌────▼────┐  ┌──────▼──────┐  ┌────▼────┐
│ Slack  │  │  Jira   │  │   AWS S3    │  │ GitHub  │
│ OAuth2 │  │ OAuth2  │  │ Credentials │  │ OAuth2  │
└────────┘  └─────────┘  └─────────────┘  └─────────┘
                                 │
                    ┌─────────────▼──────────────┐
                    │     PostgreSQL Database     │
                    │  - User Management          │
                    │  - OAuth Tokens             │
                    │  - Action Logging           │
                    │  - Webhook Events           │
                    │  - Rollback Data            │
                    └────────────────────────────┘
```

## 📋 Prerequisites

- Python 3.8+
- PostgreSQL database
- OpenAI API key
- Service credentials (Slack, Jira, AWS, GitHub)

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone https://github.com/your-org/automate-anything-agent.git
cd automate-anything-agent
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Environment Configuration

**⚠️ CRITICAL: Create Required Configuration Files**

The following files are **required** but not included in the repository for security reasons. You **must** create them before the application will work:

#### 4.1. Create Environment File

Copy the example environment file and configure your credentials:

```bash
cp .env.example .env
```

#### 4.2. Configure API Credentials

Edit `.env` with your **actual** credentials (all fields are required):

```env
# OpenAI Configuration
OPENAI_API_KEY=sk-your-openai-api-key

# Database Configuration
DATABASE_URL=postgresql://username:password@localhost:5432/automation_agent

# Application Configuration
SECRET_KEY=your-secret-key-minimum-32-characters-long

# Slack OAuth2 Configuration
SLACK_CLIENT_ID=your_slack_client_id
SLACK_CLIENT_SECRET=your_slack_client_secret

# Jira OAuth2 Configuration
JIRA_CLIENT_ID=your_jira_client_id
JIRA_CLIENT_SECRET=your_jira_client_secret
JIRA_BASE_URL=https://your-domain.atlassian.net

# AWS Configuration
AWS_ACCESS_KEY_ID=your_aws_access_key
AWS_SECRET_ACCESS_KEY=your_aws_secret_key
AWS_S3_BUCKET=your-s3-bucket-name

# GitHub OAuth2 Configuration
GITHUB_CLIENT_ID=your_github_client_id
GITHUB_CLIENT_SECRET=your_github_client_secret
```

#### 4.3. Additional Security Considerations

For production deployments, also ensure:

- Change the `SECRET_KEY` to a random 32+ character string
- Use strong database passwords
- Enable SSL/TLS for database connections
- Store secrets in a secure vault (AWS Secrets Manager, etc.)

### 5. Database Setup

**Prerequisites**: Ensure PostgreSQL is running and accessible with the credentials in your `.env` file.

Initialize the database:

```bash
python main.py init
```

### 6. User Registration

Register a new user:

```bash
python main.py register
```

### 7. Required API Credentials Setup

Before using the automation features, you **must** obtain and configure API credentials for the services you want to integrate:

#### 7.1. LLM Provider Configuration

The agent supports multiple LLM providers. Choose one and configure:

**OpenAI:**
- Visit https://platform.openai.com/api-keys
- Create a new API key
- Set `LLM_PROVIDER=openai` and `LLM_API_KEY=sk-...`
- Use models like `gpt-3.5-turbo`, `gpt-4`, etc.

**DeepSeek:**
- Visit https://platform.deepseek.com/
- Get your API key
- Set `LLM_PROVIDER=deepseek` and `LLM_API_KEY=sk-...`
- Use models like `deepseek-chat`, `deepseek-coder`

**Qwen (Alibaba Cloud):**
- Visit https://dashscope.aliyuncs.com/
- Get your API key
- Set `LLM_PROVIDER=qwen` and `LLM_API_KEY=sk-...`
- Use models like `qwen-turbo`, `qwen-plus`

**Groq:**
- Visit https://console.groq.com/
- Get your API key
- Set `LLM_PROVIDER=groq` and `LLM_API_KEY=gsk_...`
- Use models like `llama2-70b-4096`, `mixtral-8x7b-32768`

**Ollama (Local):**
- Install Ollama: https://ollama.ai/
- Run: `ollama serve`
- Set `LLM_PROVIDER=ollama` and `LLM_MODEL=llama2`
- No API key required for local models

**Other Providers:**
- Together AI: Set `LLM_PROVIDER=together`
- Perplexity: Set `LLM_PROVIDER=perplexity`  
- OpenRouter: Set `LLM_PROVIDER=openrouter`
- Custom endpoint: Set `LLM_PROVIDER=local` and `LLM_BASE_URL=your_endpoint`

#### 💡 **Recommended Models for Automation:**

| Provider | Model | Best For | Cost |
|----------|-------|----------|------|
| OpenAI | `gpt-3.5-turbo` | General automation, fast | Low |
| OpenAI | `gpt-4` | Complex reasoning | High |
| DeepSeek | `deepseek-chat` | Cost-effective alternative | Very Low |
| Qwen | `qwen-turbo` | Fast Asian language support | Low |
| Groq | `llama2-70b-4096` | Very fast inference | Low |
| Ollama | `llama2`, `codellama` | Local/offline use | Free |

#### 🔧 **Function Calling Support:**
- **Native support**: OpenAI models, some OpenAI-compatible APIs
- **Simulated support**: All other models via prompt engineering
- **Recommendation**: Use OpenAI or DeepSeek for best function calling experience

📘 **For detailed LLM provider setup and cost comparisons, see [LLM_PROVIDERS.md](LLM_PROVIDERS.md)**

#### 7.2. Service-Specific Setup
Follow the service configuration guides below to obtain OAuth2 credentials.

## 🎯 Usage

### CLI Commands

#### Basic Commands

```bash
# Initialize database
python main.py init

# Register user
python main.py register

# Login
python main.py login

# Show status
python main.py status

# Show examples
python main.py examples
```

#### OAuth2 Service Connection

```bash
# Connect to Slack
python main.py connect slack

# Connect to Jira
python main.py connect jira

# Connect to GitHub
python main.py connect github
```

#### Automation Execution

```bash
# Execute automation command
python main.py execute "Summarize unread Slack messages from #urgent and create a high-priority Jira ticket if any contain the word 'outage'"

# View automation history
python main.py history

# Rollback an action
python main.py rollback 123
```

### Example Commands

The agent understands natural language commands and automatically determines which APIs to call:

1. **Slack + Jira Integration**:
   ```
   "Summarize unread Slack messages from #urgent and create a high-priority Jira ticket if any contain the word 'outage'"
   ```

2. **Slack + S3 Integration**:
   ```
   "Get messages from #general channel and upload a summary to S3 as daily-report.txt"
   ```

3. **GitHub + S3 Integration**:
   ```
   "Search GitHub for python automation repositories and save the top 5 to S3"
   ```

4. **Multi-channel Analysis**:
   ```
   "Check #alerts channel for critical messages and create Jira tickets for each urgent issue"
   ```

5. **Sentiment Analysis**:
   ```
   "Analyze sentiment of messages in #feedback channel and create a summary report"
   ```

### FastAPI Server

Start the webhook server:

```bash
python server.py
```

The server provides:

- **OAuth2 Callbacks**: `/auth/{service}/callback`
- **Webhooks**: `/webhooks/{service}`
- **API Endpoints**: `/api/execute`, `/api/rollback/{action_id}`, `/api/history`
- **Documentation**: `/docs`

#### API Usage

```bash
# Execute automation via API
curl -X POST "http://localhost:8000/api/execute" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"command": "Get Slack messages from #urgent"}'

# Rollback action
curl -X POST "http://localhost:8000/api/rollback/123" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Testing rollback"}'
```

## 🔧 Service Configuration

**⚠️ CRITICAL SETUP REQUIRED**: These configurations are **mandatory** for the automation features to work.

### Slack Setup

1. **Create a Slack App** at https://api.slack.com/apps
2. **Configure OAuth2 scopes**: `channels:read`, `chat:write`, `users:read`, `channels:history`
3. **Set redirect URI**: `http://localhost:8000/auth/slack/callback`
4. **Add webhook URL**: `http://localhost:8000/webhooks/slack`
5. **Copy credentials** to your `.env` file:
   - `SLACK_CLIENT_ID` = Your app's Client ID
   - `SLACK_CLIENT_SECRET` = Your app's Client Secret

### Jira Setup

1. **Create an OAuth2 application** in Jira (Settings → Apps → OAuth credentials)
2. **Configure scopes**: `read:jira-work`, `write:jira-work`, `manage:jira-project`
3. **Set redirect URI**: `http://localhost:8000/auth/jira/callback`
4. **Add webhook URL**: `http://localhost:8000/webhooks/jira`
5. **Copy credentials** to your `.env` file:
   - `JIRA_CLIENT_ID` = Your OAuth2 Client ID
   - `JIRA_CLIENT_SECRET` = Your OAuth2 Client Secret
   - `JIRA_BASE_URL` = Your Jira instance URL (e.g., https://yourcompany.atlassian.net)

### AWS S3 Setup

1. **Create an IAM user** with S3 permissions
2. **Create an S3 bucket** for file storage
3. **Generate access credentials**
4. **Copy credentials** to your `.env` file:
   - `AWS_ACCESS_KEY_ID` = Your IAM user's access key
   - `AWS_SECRET_ACCESS_KEY` = Your IAM user's secret key
   - `AWS_S3_BUCKET` = Your S3 bucket name
   - `AWS_REGION` = Your preferred AWS region

### GitHub Setup

1. **Create a GitHub OAuth App** (Settings → Developer settings → OAuth Apps)
2. **Configure scopes**: `repo`, `read:user`, `read:org`
3. **Set redirect URI**: `http://localhost:8000/auth/github/callback`
4. **Add webhook URL**: `http://localhost:8000/webhooks/github`
5. **Copy credentials** to your `.env` file:
   - `GITHUB_CLIENT_ID` = Your OAuth App Client ID
   - `GITHUB_CLIENT_SECRET` = Your OAuth App Client Secret

### 🔒 Security Notes

- **Never commit** your `.env` file or any files containing API keys
- **Use separate credentials** for development and production
- **Regularly rotate** API keys and secrets
- **Enable 2FA** on all service accounts where possible
- **Review permissions** regularly and use minimum required scopes

## 🔄 Rollback System

Every automation action is logged with rollback capabilities:

- **Automatic Rollback Detection**: Actions that modify external services are marked as rollback-able
- **Comprehensive Logging**: All API calls, parameters, and responses are stored
- **Safe Rollback**: Rollback operations are executed in reverse order
- **Audit Trail**: Complete history of actions and rollbacks

### Rollback Examples

```bash
# View rollback-able actions
python main.py history

# Rollback specific action
python main.py rollback 123

# Rollback with reason
python main.py rollback 123 --reason "Incorrect ticket created"
```

## 📊 Monitoring & Logging

### Structured Logging

The agent uses structured logging with support for both JSON (production) and human-readable (development) formats:

```bash
# JSON logging (production)
LOG_FORMAT=json python server.py

# Human-readable logging (development)
LOG_FORMAT=console python server.py
```

### Database Monitoring

All actions are logged to PostgreSQL with comprehensive metadata:

- User actions and authentication
- API calls and responses
- Webhook events and processing
- Error tracking and debugging
- Performance metrics

### Health Checks

```bash
# Check API health
curl http://localhost:8000/health

# Check database connectivity
python main.py status
```

## 🔒 Security

### Authentication & Authorization

- **JWT Tokens**: Secure user authentication
- **OAuth2 Flows**: Secure integration with external services
- **Token Refresh**: Automatic token renewal
- **Scope Validation**: Granular permission control

### Webhook Security

- **Signature Verification**: Validate webhook authenticity
- **Rate Limiting**: Prevent abuse
- **CORS Configuration**: Control cross-origin requests

### Data Protection

- **Encrypted Storage**: Sensitive data encryption
- **Audit Logging**: Complete action history
- **Access Control**: User-based data isolation

## 🧪 Testing

Run the test suite:

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_agent.py
```

## 📈 Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "server.py"]
```

### Environment Variables

For production, ensure all environment variables are properly configured:

```bash
# Production settings
DEBUG=false
LOG_LEVEL=INFO
LOG_FORMAT=json

# Security
SECRET_KEY=your-production-secret-key-32-chars-minimum

# Database
DATABASE_URL=postgresql://user:pass@db-host:5432/automation_agent

# External URLs (use your production domain)
SLACK_REDIRECT_URI=https://your-domain.com/auth/slack/callback
JIRA_REDIRECT_URI=https://your-domain.com/auth/jira/callback
GITHUB_REDIRECT_URI=https://your-domain.com/auth/github/callback
```

### Scaling Considerations

- **Database Connection Pooling**: Configure appropriate pool sizes
- **Redis Caching**: Add Redis for session management
- **Load Balancing**: Use multiple server instances
- **Background Tasks**: Consider Celery for heavy processing
- **Monitoring**: Add APM tools like DataDog or New Relic

## 🔍 Troubleshooting

### Common Configuration Issues

**❌ "No valid token found" errors:**
- Ensure you've completed OAuth2 authentication: `python main.py connect <service>`
- Check that your API credentials in `.env` are correct
- Verify redirect URIs match exactly in service configurations

**❌ "Database connection failed":**
- Ensure PostgreSQL is running
- Check database credentials in `.env`
- Verify database exists: `createdb automation_agent`

**❌ "LLM API errors":**
- Verify your LLM API key and provider in `.env`
- Check your account has sufficient credits (for paid providers)
- Ensure the API key has proper permissions
- For local models (Ollama), ensure the service is running
- Verify the model name is correct for your provider

**❌ "Import errors":**
- Ensure you've installed all requirements: `pip install -r requirements.txt`
- Check that you're in the correct virtual environment
- Try reinstalling dependencies: `pip install --force-reinstall -r requirements.txt`

**❌ "Permission denied" for services:**
- Review OAuth2 scopes in service configurations
- Ensure webhook URLs are accessible (use ngrok for local development)
- Check service-specific permission settings

### Missing File Checklist

Before running the application, ensure these files exist:

- [ ] `.env` (copied from `.env.example` and configured)
- [ ] PostgreSQL database running and accessible
- [ ] Virtual environment activated
- [ ] All dependencies installed (`pip install -r requirements.txt`)
- [ ] Database initialized (`python main.py init`)
- [ ] User registered (`python main.py register`)
- [ ] Services connected (`python main.py connect <service>`)

### Getting Help

If you encounter issues:

1. **Check the application logs**: `tail -f logs/automation.log`
2. **Enable debug mode**: Set `DEBUG=true` in `.env`
3. **Test database connection**: `python main.py status`
4. **Verify service connections**: `python main.py status`
5. **Check `.gitignore` compliance**: Ensure no sensitive files are tracked

### Critical Files NOT in Repository

These files must be created manually (see `.gitignore`):

- `.env` - Environment variables and API keys
- Any `*.key`, `*.pem` files - SSL certificates and private keys
- `config.json`, `settings.json` - Configuration files with secrets
- Database files (`*.db`, `*.sqlite`)
- Log files (`*.log`)
- Credential files in `secrets/` or `credentials/` directories

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Commit changes: `git commit -m 'Add amazing feature'`
4. Push to branch: `git push origin feature/amazing-feature`
5. Open a Pull Request

### Development Setup

```bash
# Install development dependencies
pip install -e ".[dev]"

# Run linting
black src/ tests/
isort src/ tests/
flake8 src/ tests/
mypy src/

# Run tests
pytest
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- OpenAI for GPT-4 and function calling capabilities
- FastAPI for the excellent web framework
- Typer for the beautiful CLI interface
- All the open-source libraries that make this possible

## 📞 Support

- Create an issue for bug reports
- Start a discussion for feature requests
- Check the documentation for common questions

---

**Happy Automating! 🤖✨**
