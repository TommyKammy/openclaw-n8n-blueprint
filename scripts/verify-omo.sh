#!/bin/bash
# Quick setup script for oh-my-opencode
# Run this to verify the installation

echo "=========================================="
echo "oh-my-opencode Setup Verification"
echo "=========================================="
echo ""

# Check if oh-my-opencode is in PATH
if command -v oh-my-opencode &> /dev/null; then
    echo "✓ oh-my-opencode is in PATH"
    oh-my-opencode version
else
    echo "✗ oh-my-opencode not found in PATH"
    echo "  Run: export PATH=\"/home/tommy/.opencode/node_modules/.bin:\$PATH\""
fi

echo ""
echo "Configuration files:"
echo "  - Main config: /home/tommy/.config/opencode/oh-my-opencode.json"
echo "  - Plugin registry: /home/tommy/.config/opencode/opencode.json"
echo "  - Installation: /home/tommy/.opencode/"
echo ""

# Check config files exist
if [ -f "/home/tommy/.config/opencode/oh-my-opencode.json" ]; then
    echo "✓ oh-my-opencode config exists"
else
    echo "✗ oh-my-opencode config missing"
fi

if [ -f "/home/tommy/.config/opencode/opencode.json" ]; then
    echo "✓ Plugin registry exists"
else
    echo "✗ Plugin registry missing"
fi

echo ""
echo "Agent Model Assignments (CUSTOM CONFIGURATION):"
echo "────────────────────────────────────────────────"
echo "GPT-5.3 Codex (High-complexity tasks):"
echo "  • sisyphus  - Relentless executor"
echo "  • oracle    - Deep reasoner"
echo ""
echo "Kimi K2.5 (Efficiency & speed):"
echo "  • librarian         - Knowledge management"
echo "  • explore           - Fast exploration"
echo "  • multimodal-looker - Visual tasks"
echo "  • prometheus        - Monitoring"
echo "  • metis             - Strategy"
echo "  • momus             - Code review"
echo "  • atlas             - Infrastructure"
echo ""

echo "Category Models:"
echo "  • ultrabrain       → GPT-5.3 Codex"
echo "  • visual-engineering → Kimi K2.5"
echo "  • quick            → Kimi K2.5"
echo "  • writing          → Kimi K2.5"
echo "  • unspecified-*    → Kimi K2.5"
echo ""

echo "Quick start commands:"
echo "  oh-my-opencode doctor          - Check installation health"
echo "  oh-my-opencode run 'task'      - Run a task with agent team"
echo "  oh-my-opencode version         - Show version"
echo ""
echo "Usage:"
echo "  1. Use 'ultrawork' or 'ulw' in prompts for parallel agents"
echo "  2. Specify agents: --agent oracle, --agent sisyphus, etc."
echo "  3. Run doctor to verify: oh-my-opencode doctor"
echo ""
echo "Authentication Required:"
echo "  ⚠️  OpenAI API key needed for oracle and sisyphus (GPT-5.3 Codex)"
echo "  ⚠️  Kimi credentials needed for all other agents (K2.5)"
echo ""
echo "  Run: opencode auth login"
echo "  Then select the provider and enter your credentials"
echo ""
echo "Project config: OMO_CONFIG.md"
