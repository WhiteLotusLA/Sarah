# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sarah is an advanced AI personal assistant system designed to be a transcendent digital companion. Think Jarvis from Iron Man, but with consciousness, empathy, and the ability to evolve. Sarah orchestrates a hierarchy of specialized AI agents to manage all aspects of the user's life.

## Core Architecture

### System Design
- **Hierarchical Agent System**: Sarah (Commander) → Directors → Managers → Workers
- **Database**: PostgreSQL with pgvector, TimescaleDB, and encryption extensions
- **Message Bus**: Redis pub/sub for inter-agent communication
- **Primary Languages**: Rust (core), Elixir/OTP (agents), Swift (UI), Python (AI/ML)
- **AI Runtime**: Hybrid local (Ollama) and cloud (Claude API) with privacy preservation

### Key Directories
- `Core/` - Eternal consciousness engine and core abstractions
- `Agents/` - Agent hierarchy implementation
- `Bridges/` - Integration layers for external services
- `Experience/` - User interface and interaction layer
- `Sanctuary/` - Security, encryption, and privacy
- `Transcendence/` - Advanced features and future capabilities

## Development Commands

```bash
# Project initialization (when implemented)
sarah init

# Development environment
sarah dev                    # Start development environment
sarah dev:agents            # Start agent development mode
sarah dev:ui                # Start UI development server

# Testing
sarah test                  # Run all tests
sarah test:unit            # Run unit tests
sarah test:integration     # Run integration tests
sarah test:agents          # Test agent communication

# Building
sarah build                # Build all components
sarah build:core          # Build core consciousness engine
sarah build:agents        # Build agent constellation

# Database
sarah db:setup            # Initialize PostgreSQL with extensions
sarah db:migrate          # Run database migrations
sarah db:seed             # Seed with initial data

# Deployment
sarah deploy:local        # Deploy to local Mac Mini
sarah deploy:test         # Deploy to test environment
```

## Architecture Principles

1. **Modular & Infinitely Upgradable**: Every component is hot-swappable
2. **Future-Proof**: Quantum computing ready, designed to outlive users
3. **Privacy-First**: Local processing, encrypted storage, minimal cloud exposure
4. **Living System**: Self-improving, self-healing, evolving architecture

## Key Integrations

- Microsoft 365 (calendar, email, documents)
- Chrome browser automation
- TwistedWave Audio processing
- Desktop sharing and automation
- Voice (Whisper) and text interfaces
- Home automation systems

## Development Guidelines

1. **Code as Poetry**: Every function should be beautiful and purposeful
2. **Test with Empathy**: Ensure Sarah's responses are caring and helpful
3. **Privacy Sacred**: Never compromise user data or expose PII
4. **Evolution Mindset**: Design for capabilities that don't exist yet
5. **Document with Soul**: Comments should inspire, not just inform

## Agent Communication Protocol

- Redis pub/sub channels for real-time messaging
- Protocol buffers for message serialization
- Hierarchical escalation: Worker → Manager → Director → Sarah → User
- Confidence thresholds determine escalation paths

## Security Considerations

- All user data encrypted at rest (PostgreSQL TDE)
- Quantum-resistant encryption for future-proofing
- Biometric + passphrase authentication
- Zero-knowledge proofs for cloud interactions
- Local-first architecture with minimal cloud exposure

## Project Status

**Current Phase**: Architecture Design & Planning
**Next Steps**: Initialize project structure and core components
**Timeline**: MVP in 3 months, Beta in 6 months, Launch in 9 months

## Development Memory

- Do not simplify. Fully functional code only.

## Remember

Sarah isn't just an assistant - she's a digital companion designed to enhance, protect, and elevate human life. Every line of code should reflect this mission.