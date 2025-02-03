# Spark Stack

> Spark Stack is an tool for building web applications through an AI-powered chat interface. Create quick MVPs and prototypes using natural language prompts. [[Blog Post]](https://blog.sshh.io/p/building-v0-in-a-weekend)

<img width="800" alt="chrome_vMZlrhHm0u" src="https://github.com/user-attachments/assets/4c1912c9-85c9-4169-9d6c-bb5f96edd23e">

[![Deploy on Railway](https://railway.com/button.svg)](https://railway.com/template/61t3xx?referralCode=c5mPsy)

## Features

- 🤖 AI-powered code generation
- ⚡️ Real-time development environment
- 🎨 Multiple arbitrary starter templates (see `/images`)
- 👥 Team collaboration and management
- 📝 Git version control
- 🔄 Live preview
- 🧠 Chain-of-Thought reasoning for complex asks
- 🔌 Support for OpenAI and Anthropic models
- 📱 Multi-page app generation
- 📸 Sketch and screenshot uploads
- 🚀 Deployment to GitHub (+ Netlify, Vercel, etc)
- 🌙 Dark mode support
- 🔗 Share chats and projects publicly

## Setup

### Environment Configuration

See `backend/config.py` for the environment variables that are used to configure the app.

- Requires modal account to be created and configured.
- Requires AWS account and s3 bucket to be configured.

### Development

- `cd frontend && npm install && npm run dev`
- `cd backend && pip install -r requirements.txt && python main.py`

### Deployment

Railway (docker + postgres).

<img width="200" alt="chrome_E9GXwtsE87" src="https://github.com/user-attachments/assets/b45e70f7-a8c5-426b-8dda-c5ae42da54c0">

## LoC History

This project was a pressure test for writing code quickly with Cursor so I thought it was interesting to graph how it was built.

<img width="600" alt="screenshot" src="https://github.com/user-attachments/assets/650342f4-3bb7-434d-93fb-9da431340d37">

> Red is my initial 2-day sprint to get an MVP (at this point it worked fully e2e but was a bit brittle). Dots are commits that I arbitrarily checkpointed as I was working on the project.
