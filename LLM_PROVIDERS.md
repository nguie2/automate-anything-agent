# 🤖 LLM Provider Configuration Guide

This automation agent supports multiple LLM providers, giving you flexibility in cost, performance, and deployment options.

## 🌟 Supported Providers

### OpenAI (Recommended for beginners)
```bash
LLM_PROVIDER=openai
LLM_API_KEY=sk-your_openai_key_here
LLM_MODEL=gpt-3.5-turbo  # or gpt-4, gpt-4-turbo
```
- ✅ Native function calling support
- ✅ High reliability
- ❌ Higher cost
- 🔗 Get API key: https://platform.openai.com/api-keys

### DeepSeek (Best value for money)
```bash
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your_deepseek_key_here
LLM_MODEL=deepseek-chat  # or deepseek-coder
```
- ✅ Very low cost (~1/10th of OpenAI)
- ✅ Good performance
- ✅ Function calling support
- 🔗 Get API key: https://platform.deepseek.com/

### Qwen (Alibaba Cloud)
```bash
LLM_PROVIDER=qwen
LLM_API_KEY=sk-your_qwen_key_here
LLM_MODEL=qwen-turbo  # or qwen-plus, qwen-max
```
- ✅ Good for Asian languages
- ✅ Fast inference
- ✅ Competitive pricing
- 🔗 Get API key: https://dashscope.aliyuncs.com/

### Groq (Fastest inference)
```bash
LLM_PROVIDER=groq
LLM_API_KEY=gsk_your_groq_key_here
LLM_MODEL=llama2-70b-4096  # or mixtral-8x7b-32768
```
- ✅ Extremely fast inference
- ✅ Low cost
- ⚠️ Rate limits on free tier
- 🔗 Get API key: https://console.groq.com/

### Ollama (Local/Offline)
```bash
LLM_PROVIDER=ollama
LLM_API_KEY=dummy  # Not used for local models
LLM_BASE_URL=http://localhost:11434/v1
LLM_MODEL=llama2  # or codellama, mistral, etc.
```
- ✅ Completely free
- ✅ Privacy - runs locally
- ✅ No internet required
- ❌ Requires powerful hardware
- 🔗 Install: https://ollama.ai/

### Together AI
```bash
LLM_PROVIDER=together
LLM_API_KEY=your_together_key_here
LLM_MODEL=meta-llama/Llama-2-70b-chat-hf
```
- ✅ Open source models
- ✅ Good performance
- 🔗 Get API key: https://api.together.xyz/

### Perplexity
```bash
LLM_PROVIDER=perplexity
LLM_API_KEY=pplx-your_key_here
LLM_MODEL=llama-2-70b-chat
```
- ✅ Web search capabilities
- ✅ Fast inference
- 🔗 Get API key: https://www.perplexity.ai/

### OpenRouter (Access to many models)
```bash
LLM_PROVIDER=openrouter
LLM_API_KEY=sk-or-your_key_here
LLM_MODEL=anthropic/claude-3-sonnet  # or many others
```
- ✅ Access to 100+ models
- ✅ Pay-per-use pricing
- ✅ Easy model switching
- 🔗 Get API key: https://openrouter.ai/

## 💰 Cost Comparison (approximate, per 1M tokens)

| Provider | Model | Input | Output | Notes |
|----------|-------|-------|---------|-------|
| OpenAI | gpt-3.5-turbo | $0.50 | $1.50 | Baseline |
| OpenAI | gpt-4 | $10.00 | $30.00 | Premium |
| DeepSeek | deepseek-chat | $0.07 | $0.28 | 🏆 Best value |
| Qwen | qwen-turbo | $0.12 | $0.12 | Flat rate |
| Groq | llama2-70b | $0.70 | $0.80 | Very fast |
| Ollama | Any model | $0.00 | $0.00 | 🏆 Free |

## ⚡ Performance Comparison

| Provider | Speed | Quality | Function Calling | Privacy |
|----------|-------|---------|------------------|---------|
| OpenAI | Good | Excellent | Native | Cloud |
| DeepSeek | Good | Very Good | Native | Cloud |
| Groq | Excellent | Good | Simulated | Cloud |
| Ollama | Varies | Good | Simulated | Local |

## 🛠️ Setup Instructions

### Option 1: OpenAI (Easiest)
1. Sign up at https://platform.openai.com/
2. Go to API Keys section
3. Create new key
4. Set in `.env`: `LLM_PROVIDER=openai` and `LLM_API_KEY=sk-...`

### Option 2: DeepSeek (Best Value)
1. Sign up at https://platform.deepseek.com/
2. Get API key from dashboard
3. Set in `.env`: `LLM_PROVIDER=deepseek` and `LLM_API_KEY=sk-...`

### Option 3: Ollama (Free/Local)
1. Install Ollama: `curl -fsSL https://ollama.ai/install.sh | sh`
2. Start service: `ollama serve`
3. Download model: `ollama pull llama2`
4. Set in `.env`: `LLM_PROVIDER=ollama` and `LLM_MODEL=llama2`

## 🔧 Model Recommendations

### For Automation Tasks:
- **Production**: `deepseek-chat` (great balance of cost/performance)
- **Development**: `gpt-3.5-turbo` (reliable and fast)
- **Budget**: Ollama `llama2` (free but requires good hardware)
- **Speed**: Groq `llama2-70b-4096` (fastest inference)

### For Code Generation:
- **Best**: `deepseek-coder` or `gpt-4`
- **Budget**: Ollama `codellama`

### For Multilingual:
- **Chinese/Asian**: `qwen-turbo`
- **General**: `gpt-3.5-turbo` or `deepseek-chat`

## 🚨 Important Notes

1. **Function Calling**: OpenAI and DeepSeek have the best native support. Others use prompt engineering which works but may be less reliable.

2. **Rate Limits**: Free tiers have limits. For production, use paid tiers.

3. **Local Models**: Ollama requires significant RAM (8GB+ for 7B models, 32GB+ for 70B models).

4. **API Compatibility**: Most providers use OpenAI-compatible APIs, making switching easy.

5. **Fallback**: Always have a backup provider configured in case your primary provider has issues.

## 🔄 Switching Providers

To switch providers, just update your `.env` file:

```bash
# From OpenAI to DeepSeek
LLM_PROVIDER=deepseek
LLM_API_KEY=sk-your_deepseek_key
LLM_MODEL=deepseek-chat

# Restart the application
python main.py
```

No code changes required! The agent automatically adapts to the new provider.

## 📊 Testing Your Setup

After configuring, test with:

```bash
# Test the LLM connection
python main.py status

# Run a simple automation
python main.py execute "analyze this text: Hello world"
```

## 🆘 Troubleshooting

**Common Issues:**

1. **API Key Invalid**: Double-check your API key format and provider
2. **Model Not Found**: Ensure the model name is correct for your provider
3. **Rate Limited**: Upgrade your plan or switch to a different provider
4. **Ollama Not Working**: Make sure `ollama serve` is running and model is downloaded

**Getting Help:**
- Check provider documentation
- Verify your account status and credits
- Test with a simple curl command first
- Check the application logs for detailed errors 