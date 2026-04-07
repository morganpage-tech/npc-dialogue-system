# Contributing to NPC Dialogue System

Thank you for your interest in contributing! This project is built to help indie developers create immersive AI-powered RPGs.

## 🤝 How to Contribute

### Reporting Bugs

Before creating bug reports, please check existing issues.

**Use the template:**
```markdown
**Describe the bug**
A clear and concise description of what the bug is.

**To Reproduce**
Steps to reproduce the behavior:
1. Go to '...'
2. Click on '....'
3. Scroll down to '....'
4. See error

**Expected behavior**
A clear and concise description of what you expected to happen.

**Screenshots**
If applicable, add screenshots to help explain your problem.

**Environment:**
 - OS: [e.g., macOS 14, Ubuntu 22.04]
 - Python version: [e.g., 3.12.3]
 - Ollama version: [e.g., 0.5.7]
 - Model: [e.g., llama3.2:1b]
```

### Suggesting Enhancements

We love feature requests! Before suggesting:

1. **Check the roadmap** - See PROJECT_SUMMARY.md for planned features
2. **Search issues** - Make sure it hasn't been suggested
3. **Think about use case** - Who would benefit? How often?

**Feature request template:**
```markdown
**Is your feature request related to a problem?**
A clear and concise description of what the problem is.

**Describe the solution you'd like**
A clear and concise description of what you want to happen.

**Describe alternatives you've considered**
A clear and concise description of any alternative solutions or features you've considered.

**Additional context**
Add any other context, screenshots, or examples about the feature request here.
```

### Pull Requests

We welcome pull requests! Here's how to get started:

1. **Fork the repository**
   ```bash
   gh repo fork
   ```

2. **Clone your fork**
   ```bash
   git clone https://github.com/<your-username>/npc-dialogue-system.git
   cd npc-dialogue-system
   git checkout -b your-feature-branch
   ```

3. **Make your changes**
   - Write clean, readable code
   - Add comments for complex logic
   - Update documentation if needed
   - Test on multiple models if applicable

4. **Write tests** (if applicable)
   ```bash
   python3 test_structure.py
   ```

5. **Commit your changes**
   ```bash
   git add .
   git commit -m "Add: Your feature description"
   ```

6. **Push to your fork**
   ```bash
   git push origin your-feature-branch
   ```

7. **Create Pull Request**
   ```bash
   gh pr create --title "Add: Your feature" --body "Description..."
   ```

## 📝 Code Style

### Python
- Follow PEP 8 guidelines
- Use descriptive variable names
- Add docstrings to functions
- Keep functions focused and small
- Maximum line length: 100 characters

### Character Cards
- Use JSON format (SillyTavern compatible)
- Include all required fields
- Add example dialogue (`mes_example`)
- Use consistent naming conventions

## 🧪 Testing

### Manual Testing
```bash
# Test core system
python3 test_structure.py

# Setup verification
python3 setup_check.py

# Run demo with different models
python3 main.py
# Then: /switch <character>
```

### Test Checklist
- [ ] Works on Python 3.9+
- [ ] Works on M1 MacBook Air (both 8GB and 16GB)
- [ ] Tested with at least 2 different Ollama models
- [ ] Documentation updated if needed
- [ ] New character cards include examples

## 📚 Documentation

### When to Update Docs

Update documentation when you:
- Add a new feature
- Change an API function
- Add a new example
- Fix a significant bug

### Files to Update

- **README.md** - User-facing changes
- **INTEGRATION_GUIDE.md** - New integration methods
- **PROJECT_SUMMARY.md** - Roadmap changes
- **CHANGELOG.md** - Version history

## 🎯 Areas We Need Help With

### High Priority
- [ ] Unity C# integration examples
- [ ] Godot GDScript integration examples
- [ ] Relationship tracking system
- [ ] Lore/knowledge base (RAG) implementation

### Medium Priority
- [ ] Voice synthesis integration
- [ ] Streaming responses implementation
- [ ] Character personality fine-tuning (LoRA)
- [ ] Performance benchmarks across hardware

### Low Priority
- [ ] Web-based character editor
- [ ] Visual conversation browser
- [ ] Additional example characters

## 🤝 Community

### Getting in Touch

- **Issues**: For bugs and feature requests
- **Discussions**: For questions and ideas
- **Pull Requests**: For code contributions

### Code of Conduct

Be respectful, welcoming, and inclusive. We're all here to build better games!

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to NPC Dialogue System! Let's build the next generation of immersive RPGs together! 🎮✨
