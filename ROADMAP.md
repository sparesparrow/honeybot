# Honeybot Roadmap

This document outlines the implementation roadmap for honeybot, a modular personal guardian bot with sensor integration and multi-channel notifications.

## Project Overview

**Main Issue**: [#8](https://github.com/sparesparrow/honeybot/issues/8) - Roadmap: modular guardian bot core, sensors, and Telegram alerts

Honeybot is envisioned as a "personal guardian" that sits between sensors (camera, motion, online activity) and multiple notification channels (Telegram, Matrix, email), featuring:
- Modular core daemon architecture
- Pluggable sensor adapters
- Rules engine for event evaluation
- Multiple notification backends
- Guardian personality profiles

## Implementation Milestones

### [Milestone 1: Core service and config (#9)](https://github.com/sparesparrow/honeybot/issues/9)
- Implement long-running honeybot daemon with event loop
- Config file for global settings and enabled modules
- Define internal event schema (source, type, payload, severity, timestamp)
- Structured logging and health check endpoint

### [Milestone 2: Sensor modules (#10)](https://github.com/sparesparrow/honeybot/issues/10)
- Webhook sensor module for HTTP POSTs (ESP32CAM/devices)
- Filesystem/snapshot sensor watching directories
- System auth sensor parsing auth logs for repeated failures

### Milestone 3: Rule engine (#11 - to be created)
- Implement rule engine with YAML/JSON configuration
- Conditions on event fields (time ranges, severity, source)
- Actions referencing notification backends and templates
- Support escalation logic (if N events in T minutes, raise severity)

### Milestone 4: Telegram bot backend (#12 - to be created)
- Integrate Telegram bot as primary notification backend
- Support sending alerts with text and images
- Basic commands: arm/disarm, set home/away mode, query recent events

### Milestone 5: Guardian personalities (#13 - to be created)
- Implement profile system for predefined guardian personas
- Different message templates and rule sets per persona
- User customizable personality definitions

### Milestone 6: Packaging and examples (#14 - to be created)
- Systemd service unit and documentation
- Example configs for Raspberry Pi home security setup
- Example configs for ESP32CAM + Telegram-only deployment
- Quickstart guide with installation and configuration

## Related Reference Projects

For inspiration and architectural patterns, see:
- AutomatedVideoSurveillance - AI face recognition + Telegram alerts
- Smart-Home-Security-using-Telegram-Chatbot - Face recognition + motion detection
- Home-Security-Bot - Raspberry Pi motion detection with mobile notifications
- Home-Security-System-using-ESP32CAM-and-Telegram - Low-cost ESP32CAM setup
- AlarmPI - Raspberry Pi intrusion detection with MQTT

## Branch Information

- **Feature Branch**: `8-roadmap-modular-guardian-bot-core-sensors-and-telegram-alerts`
- **Issue Tracking**: Milestones tracked via GitHub issues #8-#14
- **Status**: Planning and architecture phase
