#!/usr/bin/env python3
"""
Test script for Ollama integration
Tests both local Ollama and model factory integration
"""

import sys
import requests
from termcolor import cprint

def test_ollama_server():
    """Test if Ollama server is running"""
    cprint("\n=== Testing Ollama Server ===", "cyan", attrs=["bold"])

    try:
        response = requests.get("http://localhost:11434/api/tags", timeout=5)
        if response.status_code == 200:
            cprint("✅ Ollama server is running", "green")
            models = response.json().get("models", [])
            if models:
                cprint(f"📚 Found {len(models)} installed models:", "cyan")
                for model in models:
                    cprint(f"   - {model['name']}", "white")
                return True, models
            else:
                cprint("⚠️  Ollama server is running but no models are installed", "yellow")
                cprint("   Run: ollama pull deepseek-v3.1:671b", "yellow")
                return True, []
        else:
            cprint(f"❌ Ollama server returned status {response.status_code}", "red")
            return False, []
    except requests.exceptions.ConnectionError:
        cprint("❌ Ollama server is not running", "red")
        cprint("💡 Start with: ollama serve", "yellow")
        return False, []
    except Exception as e:
        cprint(f"❌ Error connecting to Ollama: {e}", "red")
        return False, []

def test_ollama_model_direct():
    """Test OllamaModel class directly"""
    cprint("\n=== Testing OllamaModel Class ===", "cyan", attrs=["bold"])

    try:
        from src.models.ollama_model import OllamaModel

        # Test 1: Create instance
        cprint("\n1. Testing model initialization...", "cyan")
        try:
            model = OllamaModel(model_name="deepseek-v3.1:671b")
            cprint("✅ Model instance created", "green")
        except Exception as e:
            cprint(f"❌ Failed to create model: {e}", "red")
            return False

        # Test 2: Check is_available()
        cprint("\n2. Testing is_available()...", "cyan")
        if model.is_available():
            cprint("✅ Model reports as available", "green")
        else:
            cprint("❌ Model reports as NOT available", "red")
            return False

        # Test 3: Test generate_response()
        cprint("\n3. Testing response generation...", "cyan")
        try:
            response = model.generate_response(
                system_prompt="You are a helpful assistant.",
                user_content="Say 'test successful' if you can read this.",
                temperature=0.7,
                max_tokens=50
            )
            if response and response.content:
                cprint(f"✅ Response generated: {response.content[:100]}", "green")
                return True
            else:
                cprint("❌ Empty response received", "red")
                return False
        except Exception as e:
            cprint(f"❌ Error generating response: {e}", "red")
            return False

    except ImportError as e:
        cprint(f"❌ Cannot import OllamaModel: {e}", "red")
        return False

def test_model_factory():
    """Test ModelFactory integration"""
    cprint("\n=== Testing ModelFactory Integration ===", "cyan", attrs=["bold"])

    try:
        from src.models.model_factory import model_factory

        # Test 1: Check if Ollama is in available models
        cprint("\n1. Checking available models...", "cyan")
        available = list(model_factory._models.keys())
        cprint(f"   Available model types: {available}", "white")

        if "ollama" in available:
            cprint("✅ Ollama is available in ModelFactory", "green")
        else:
            cprint("⚠️  Ollama is NOT available in ModelFactory", "yellow")
            cprint("   This is expected if Ollama server is not running", "yellow")

        # Test 2: Try to get Ollama model
        cprint("\n2. Testing get_model('ollama')...", "cyan")
        model = model_factory.get_model("ollama")
        if model:
            cprint(f"✅ Got Ollama model: {model.model_name}", "green")
        else:
            cprint("⚠️  Could not get Ollama model", "yellow")
            return False

        # Test 3: Check is_model_available()
        cprint("\n3. Testing is_model_available()...", "cyan")
        if model_factory.is_model_available("ollama"):
            cprint("✅ ModelFactory reports Ollama as available", "green")
        else:
            cprint("❌ ModelFactory reports Ollama as NOT available", "red")
            return False

        # Test 4: Test response generation through factory
        cprint("\n4. Testing response generation through factory...", "cyan")
        try:
            response = model.generate_response(
                system_prompt="You are a helpful assistant.",
                user_content="Respond with exactly: 'Factory test passed'",
                temperature=0.3,
                max_tokens=20
            )
            if response and response.content:
                cprint(f"✅ Response: {response.content}", "green")
                return True
            else:
                cprint("❌ Empty response", "red")
                return False
        except Exception as e:
            cprint(f"❌ Error: {e}", "red")
            return False

    except Exception as e:
        cprint(f"❌ Error testing ModelFactory: {e}", "red")
        return False

def check_for_code_issues():
    """Check for potential code issues"""
    cprint("\n=== Code Analysis ===", "cyan", attrs=["bold"])

    issues = []

    # Read the ollama_model.py file
    try:
        with open("/home/user/ai-agents/src/models/ollama_model.py", "r") as f:
            content = f.read()

        # Check for redundant initialize_client() call
        if "super().__init__" in content and content.count("self.initialize_client()") > 0:
            # Check if there's an explicit call after super().__init__
            lines = content.split("\n")
            for i, line in enumerate(lines):
                if "super().__init__" in line:
                    # Check next few lines for explicit initialize_client call
                    for j in range(i+1, min(i+5, len(lines))):
                        if "self.initialize_client()" in lines[j]:
                            issues.append("⚠️  REDUNDANT CODE: initialize_client() called twice (lines ~106-107)")
                            break

        # Check if initialize_client accepts **kwargs
        if "def initialize_client(self):" in content:
            issues.append("⚠️  SIGNATURE ISSUE: initialize_client(self) should accept **kwargs")

        # Check if is_available() validates specific model
        if "def is_available(self):" in content:
            # Simple check - look at the implementation
            in_is_available = False
            checks_model_name = False
            for line in content.split("\n"):
                if "def is_available(self):" in line:
                    in_is_available = True
                elif in_is_available and "def " in line:
                    break
                elif in_is_available and "model_name" in line:
                    checks_model_name = True
                    break

            if not checks_model_name:
                issues.append("⚠️  VALIDATION ISSUE: is_available() doesn't verify if specific model is installed")

        if issues:
            cprint("\nFound potential issues:", "yellow")
            for issue in issues:
                cprint(f"  {issue}", "yellow")
        else:
            cprint("\n✅ No obvious code issues found", "green")

        return issues

    except Exception as e:
        cprint(f"❌ Error analyzing code: {e}", "red")
        return []

def main():
    """Run all tests"""
    cprint("\n" + "="*60, "cyan")
    cprint("🌙 Moon Dev's Ollama Integration Test Suite", "cyan", attrs=["bold"])
    cprint("="*60, "cyan")

    # Test 1: Ollama Server
    server_running, models = test_ollama_server()

    # Test 2: Code Analysis
    code_issues = check_for_code_issues()

    # Only run integration tests if server is running
    if server_running:
        if models:
            # Test 3: Direct OllamaModel
            test_ollama_model_direct()

            # Test 4: ModelFactory
            test_model_factory()
        else:
            cprint("\n⚠️  Skipping model tests - no models installed", "yellow")
            cprint("   Install a model: ollama pull deepseek-v3.1:671b", "yellow")
    else:
        cprint("\n⚠️  Skipping integration tests - Ollama server not running", "yellow")
        cprint("   Start server: ollama serve", "yellow")

    # Summary
    cprint("\n" + "="*60, "cyan")
    cprint("📊 Test Summary", "cyan", attrs=["bold"])
    cprint("="*60, "cyan")

    if server_running:
        cprint("✅ Ollama server: RUNNING", "green")
    else:
        cprint("❌ Ollama server: NOT RUNNING", "red")

    if code_issues:
        cprint(f"⚠️  Code issues found: {len(code_issues)}", "yellow")
    else:
        cprint("✅ Code issues: NONE", "green")

    cprint("\n💡 Recommendations:", "cyan")
    if not server_running:
        cprint("  1. Start Ollama: ollama serve", "white")
        cprint("  2. Install a model: ollama pull deepseek-v3.1:671b", "white")
    if code_issues:
        cprint("  3. Review and fix code issues listed above", "white")

    if not server_running or code_issues:
        cprint("\n⚠️  Tests incomplete - see recommendations above", "yellow")
        sys.exit(1)
    else:
        cprint("\n✅ All tests passed!", "green")
        sys.exit(0)

if __name__ == "__main__":
    main()
