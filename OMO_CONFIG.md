# oh-my-opencode Configuration for openclaw-n8n-blueprint

## Installation Complete ✓

oh-my-opencode has been successfully installed and configured for AI agent team orchestration.

## Agent Team Configuration (CUSTOM)

### Agent Model Assignment

| Agent | Model | Role | Best For |
|-------|-------|------|----------|
| **sisyphus** | **GPT-5.3 Codex** (max) | Relentless Executor | Complex, multi-step tasks requiring persistence |
| **oracle** | **GPT-5.3 Codex** (max) | Deep Reasoner | Architecture decisions, complex problem solving |
| **librarian** | Kimi K2.5 | Knowledge Manager | Documentation, research, context gathering |
| **explore** | Kimi K2.5 | Fast Explorer | Quick codebase exploration, finding files |
| **multimodal-looker** | Kimi K2.5 | Visual Assistant | UI/UX tasks, image analysis |
| **prometheus** | Kimi K2.5 | Monitor/Alert | System health, monitoring, diagnostics |
| **metis** | Kimi K2.5 | Strategist | Planning, project management, coordination |
| **momus** | Kimi K2.5 | Critic | Code review, analysis, finding issues |
| **atlas** | Kimi K2.5 | Architect | System design, infrastructure planning |

### Task Categories

| Category | Model | Use Case |
|----------|-------|----------|
| **visual-engineering** | Kimi K2.5 (max) | Complex visual/frontend tasks |
| **ultrabrain** | **GPT-5.3 Codex** (max) | Deep reasoning, research |
| **quick** | Kimi K2.5 | Fast responses, simple queries |
| **unspecified-low** | Kimi K2.5 | Default light tasks |
| **unspecified-high** | Kimi K2.5 | Default complex tasks |
| **writing** | Kimi K2.5 | Documentation, content creation |

## Model Strategy

### GPT-5.3 Codex (High-Complexity Tasks)
- **sisyphus**: Use for implementation tasks that require deep reasoning
- **oracle**: Use for architectural decisions and complex analysis
- **ultrabrain category**: Automatic selection for deep reasoning tasks

### Kimi K2.5 (Efficiency & Speed)
- All other agents use Kimi K2.5 for:
  - Faster response times
  - Cost efficiency
  - Good performance on standard coding tasks
  - Excellent for exploration and documentation

## Usage in This Project

### Magic Words

Include these keywords in your prompts to activate special behaviors:

- **`ultrawork`** or **`ulw`** - Activates parallel agents and background tasks
- Use for complex tasks that need multi-agent coordination

### Example Workflows

#### 1. Complex Feature Implementation (Uses GPT-5.3 Codex)
```
ultrawork: Implement a new scheduled job synchronization feature that 
handles webhook callbacks from n8n back to OpenClaw
```
Agents involved:
- **oracle** (GPT-5.3 Codex): Architecture design
- **sisyphus** (GPT-5.3 Codex): Implementation
- **momus** (Kimi K2.5): Code review
- **librarian** (Kimi K2.5): Documentation

#### 2. Code Review (Uses Kimi K2.5)
```
momus: Review the sync worker implementation for security issues
and code quality problems
```

#### 3. Infrastructure Planning (Uses Kimi K2.5)
```
atlas: Design a monitoring setup for the OpenClaw-n8n integration 
with health checks and alerting
```

#### 4. Bug Investigation (Uses Kimi K2.5)
```
explore: Find all files related to webhook authentication in the 
openclaw-n8n-blueprint project
```

#### 5. System Diagnostics (Uses Kimi K2.5)
```
prometheus: Check the health of the docker-compose services and 
diagnose any connection issues between containers
```

#### 6. Deep Architecture Analysis (Uses GPT-5.3 Codex)
```
oracle: Analyze the security model of the OpenClaw gateway and 
identify potential vulnerabilities in the authentication flow
```

## Configuration Files

- **Main Config**: `/home/tommy/.config/opencode/oh-my-opencode.json`
- **Plugin Registration**: `/home/tommy/.config/opencode/opencode.json`
- **Installation**: `/home/tommy/.opencode/`

## Available Commands

```bash
# Run with agent team
oh-my-opencode run "your task here"

# Check health
oh-my-opencode doctor

# Show version
oh-my-opencode version

# Get local version info
oh-my-opencode get-local-version
```

## Authentication

### Required Auth Setup

1. **OpenAI** (for GPT-5.3 Codex):
   ```bash
   opencode auth login
   # Select OpenAI and enter your API key
   ```

2. **Kimi** (for K2.5):
   ```bash
   opencode auth login
   # Select Kimi and enter your credentials
   ```

Current status:
- ⚠️ Anthropic (Claude) Auth → Auth plugin available (not used in current config)
- ○ OpenAI (ChatGPT) Auth → Auth plugin not installed (REQUIRED for oracle/sisyphus)
- ○ Kimi Auth → Auth plugin not installed (REQUIRED for all other agents)

## MCP Servers

2 built-in MCP servers are enabled:
- Provides additional tools for agent operations

## Tips for Best Results

1. **Use ultrawork/ulw** for tasks that need multiple agents or background processing
2. **Be specific** about which agent you want for specialized tasks:
   - Use `--agent oracle` for complex architectural questions
   - Use `--agent sisyphus` for difficult implementation tasks
   - Use other agents for routine tasks (faster & cheaper)
3. **Start with explore** for unfamiliar codebases
4. **Use momus** before committing critical changes
5. **Let sisyphus** handle long-running, complex implementations

## Cost Optimization Strategy

- **Kimi K2.5** for routine tasks (exploration, docs, review)
- **GPT-5.3 Codex** only when needed (complex reasoning, architecture)
- The `ultrabrain` category automatically uses GPT-5.3 Codex
- Most day-to-day tasks will use Kimi K2.5 (more cost-effective)

## Next Steps

1. **Authenticate OpenAI**: Run `opencode auth login` → select OpenAI (required for oracle/sisyphus)
2. **Authenticate Kimi**: Run `opencode auth login` → select Kimi (required for other agents)
3. **Test the setup**: `oh-my-opencode doctor` should show all auth as ✓
4. **Try a test task**: `oh-my-opencode run "explore: List all Python files in the project"`

## Troubleshooting

### If agents fail to respond
- Check authentication: `opencode auth status`
- Verify models are available: `oh-my-opencode doctor`
- Check network connectivity to model providers

### To switch back to default models
Copy the backup config or reinstall oh-my-opencode without custom configuration.
