# ArchFlow

**Voice-first AI architecture diagram designer.** Speak your requirements, get real-time system architecture diagrams powered by Amazon Nova foundation models. (Note: Live site is down due to no aws credits.)

![Python](https://img.shields.io/badge/Python-3.12-blue)
![React](https://img.shields.io/badge/React-18.2-61DAFB)
![TypeScript](https://img.shields.io/badge/TypeScript-5.3-3178C6)
![AWS SAM](https://img.shields.io/badge/AWS-SAM-FF9900)
![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.4-06B6D4)

---

[<video src="202603211326.mp4" controls width="100%"></video>](https://github.com/user-attachments/assets/f6abea43-4f61-4158-b90a-4e95942667d4)

---

## Overview

ArchFlow lets software architects and developers design system architecture diagrams through natural conversation. Instead of manually dragging boxes in a diagramming tool, you describe what you need — by voice or text — and an AI architect collaboratively designs the system, asks clarifying questions, and generates Mermaid.js diagrams in real-time.

### Key Features

- **Voice-first design** — Speak your requirements, get instant architecture diagrams
- **Multi-agent AI system** — Specialized agents for requirements analysis, architecture advice, and diagram generation
- **Real-time streaming** — Bidirectional audio via Amazon Nova Sonic 2 with sub-second latency
- **Multimodal input** — Voice, text, PDFs, images, and GitHub repos
- **Live diagram updates** — Mermaid.js diagrams update as the AI responds
- **Session persistence** — Resume conversations, browse diagram version history
- **Export** — PNG, SVG, or raw Mermaid syntax

---

## Architecture

```
┌──────────────────────────────────────────────────────┐
│                  Frontend (React)                     │
│   Voice Recording · Diagram Canvas · Chat Interface   │
└──────┬──────────────────────────┬────────────────────┘
       │ WebSocket (voice)        │ WebSocket (text) + REST
       │ ws://voice-server        │ wss://api-gateway
       │                          │
┌──────▼──────────────┐    ┌──────▼─────────────────────┐
│   Voice Server      │    │   Amazon API Gateway        │
│   (Python)          │    │   ├─ WebSocket Lambda       │
│   Nova Sonic 2      │    │   ├─ Auth Lambda            │
│   bidirectional     │    │   ├─ Upload Lambda          │
│   streaming         │    │   └─ Export Lambda          │
└──────┬──────────────┘    └──────┬─────────────────────┘
       │                          │
       └──────────┬───────────────┘
                  │
      ┌───────────▼────────────────────┐
      │      Amazon Bedrock            │
      │  Nova 2 Sonic (voice)          │
      │  Nova 2 Lite  (text/diagrams)  │
      └───┬──────────┬────────────┬────┘
          │          │            │
     ┌────▼──┐  ┌────▼────┐  ┌───▼───┐
     │Agents │  │DynamoDB │  │  S3   │
     │System │  │(state)  │  │(files)│
     └───────┘  └─────────┘  └───────┘
```

### Multi-Agent System

| Agent | Model | Role |
|-------|-------|------|
| **Orchestrator** | Nova 2 Lite | Intent classification and request routing |
| **Requirements Analyst** | Nova 2 Lite | Clarifying questions, requirements extraction |
| **Architecture Advisor** | Nova 2 Lite | Architecture recommendations, trade-off analysis |
| **Diagram Generator** | Nova 2 Lite | Mermaid.js diagram creation and updates |
| **Context Analyzer** | Nova 2 Lite | Document/image analysis, requirement extraction |

### Data Flow — Voice

1. User speaks → AudioWorklet captures 16kHz PCM
2. Base64-encoded chunks sent to voice server via WebSocket
3. Voice server streams audio to Nova Sonic 2 (bidirectional)
4. Nova responds with transcription, audio chunks, and tool calls (diagram generation)
5. Browser plays audio in real-time via Web Audio API gapless scheduling
6. Diagrams update live as the AI responds

### Data Flow — Text

1. User sends message via WebSocket to API Gateway
2. Lambda orchestrator classifies intent → routes to appropriate agent
3. Agent invokes Nova model via Bedrock Converse API
4. Response returned via WebSocket `DefaultRouteResponse`
5. Diagram and conversation state persisted to DynamoDB

---

## Tech Stack

### Frontend

| Technology | Purpose |
|------------|---------|
| React 18 + TypeScript 5.3 | UI framework |
| Vite 5 | Build tool / dev server |
| Tailwind CSS 3.4 | Styling |
| Zustand | State management |
| Mermaid.js | Diagram rendering |
| Web Audio API + AudioWorklet | Voice capture and playback |
| Radix UI | Accessible dialog / dropdown primitives |
| Lucide React | Icons |

### Backend

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Runtime |
| AWS SAM | Infrastructure as code |
| AWS Lambda (ARM64) | Serverless compute |
| Amazon API Gateway | WebSocket + REST APIs |
| Amazon Bedrock | Nova 2 Sonic + Nova 2 Lite models |
| Amazon DynamoDB | Conversation state, user accounts |
| Amazon S3 | File uploads, diagram exports |
| Pydantic 2 | Data validation |
| PyJWT + bcrypt | Authentication |
| pypdf | PDF text extraction |

---

## Project Structure

```
ArchFlow/
├── backend/
│   ├── src/
│   │   ├── agents/              # Multi-agent AI system
│   │   │   ├── orchestrator.py  # Intent routing
│   │   │   ├── requirements.py  # Requirements analyst
│   │   │   ├── advisor.py       # Architecture advisor
│   │   │   ├── diagram.py       # Diagram generator
│   │   │   └── context.py       # Document analyzer
│   │   ├── handlers/            # Lambda entry points
│   │   │   ├── websocket.py     # WebSocket handler
│   │   │   ├── auth.py          # Signup / login / verify
│   │   │   ├── upload.py        # File upload
│   │   │   └── export.py        # Diagram export
│   │   ├── services/            # Business logic
│   │   │   ├── bedrock_client.py
│   │   │   ├── voice_handler.py
│   │   │   └── dynamo_client.py
│   │   ├── models/              # Pydantic data models
│   │   └── utils/               # Logging, errors, validators
│   ├── voice_server/            # Standalone voice WebSocket server
│   │   └── server.py
│   ├── tests/
│   ├── template.yaml            # SAM template
│   ├── samconfig.toml           # SAM deploy config
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceInterface/  # Mic, waveform, transcription
│   │   │   ├── DiagramCanvas/   # Mermaid rendering + controls
│   │   │   ├── Sidebar/         # Conversation history
│   │   │   ├── InputBar/        # Text input + file upload
│   │   │   ├── Auth/            # Login / signup
│   │   │   └── shared/          # Button, Modal, Toast
│   │   ├── hooks/
│   │   │   ├── useConversation.ts    # Main orchestrator hook
│   │   │   ├── useWebSocket.ts       # Auto-reconnecting WebSocket
│   │   │   ├── useVoiceRecording.ts  # PCM capture via AudioWorklet
│   │   │   └── useFileUpload.ts      # S3 presigned URL uploads
│   │   ├── stores/              # Zustand state stores
│   │   ├── services/            # Audio playback, API clients
│   │   └── types/               # TypeScript interfaces
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── .env.example
│
└── agent-context/               # Project docs for AI assistants
```

---

## Getting Started

### Prerequisites

- **AWS account** with Amazon Bedrock access (Nova 2 Lite + Nova 2 Sonic enabled)
- **AWS CLI** configured with SSO or IAM credentials
- **SAM CLI** ([install guide](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/install-sam-cli.html))
- **Python 3.12+**
- **Node.js 18+** and npm

### 1. Deploy Backend

```bash
cd backend

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Build and deploy to AWS
sam build
sam deploy --guided
# Follow prompts to set stack name, region, and parameters
```

After deployment, note the outputs:
- `WebSocketUrl` — WebSocket endpoint for the frontend
- `ApiUrl` — REST API endpoint

### 2. Start Voice Server (Local Dev)

The voice server runs as a standalone Python process (not Lambda) for real-time bidirectional audio streaming:

```bash
cd backend

# Set required environment variables
export AWS_PROFILE=your-sso-profile
export BEDROCK_MODEL_SONIC=amazon.nova-2-sonic-v1:0
export BEDROCK_MODEL_LITE=us.amazon.nova-2-lite-v1:0
export CONVERSATION_TABLE_NAME=archflow-conversations-dev
export UPLOADS_BUCKET=archflow-uploads-dev-<account-id>

# Start voice server on ws://localhost:8081
python -m voice_server.server
```

### 3. Set Up Frontend

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.example .env.local
# Edit .env.local with your API Gateway URLs:
#   VITE_WEBSOCKET_URL=wss://<api-id>.execute-api.<region>.amazonaws.com/dev
#   VITE_API_URL=https://<api-id>.execute-api.<region>.amazonaws.com/dev
#   VITE_VOICE_WS_URL=ws://localhost:8081

# Start dev server
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

### 4. Build for Production

```bash
cd frontend
npm run build   # Output in dist/
```

---

## Environment Variables

### Backend (Lambda — set in template.yaml)

| Variable | Description | Default |
|----------|-------------|---------|
| `ENVIRONMENT` | Deployment stage | `dev` |
| `BEDROCK_MODEL_LITE` | Nova text model ID | `us.amazon.nova-2-lite-v1:0` |
| `BEDROCK_MODEL_SONIC` | Nova voice model ID | `us.amazon.nova-2-sonic-v1:0` |
| `CONVERSATION_TABLE_NAME` | DynamoDB conversations table | Auto-generated |
| `USERS_TABLE_NAME` | DynamoDB users table | Auto-generated |
| `UPLOADS_BUCKET` | S3 bucket for uploads | Auto-generated |
| `EXPORTS_BUCKET` | S3 bucket for exports | Auto-generated |
| `JWT_SECRET` | Secret for JWT signing | Set via parameter |
| `LOG_LEVEL` | Logging verbosity | `INFO` |

### Frontend (Vite — set in .env.local)

| Variable | Description |
|----------|-------------|
| `VITE_WEBSOCKET_URL` | WebSocket API Gateway URL |
| `VITE_API_URL` | REST API Gateway URL |
| `VITE_VOICE_WS_URL` | Voice server WebSocket URL |
| `VITE_MAX_FILE_SIZE` | Max upload size in bytes (default: 10MB) |

---

## Available Scripts

### Frontend

```bash
npm run dev       # Start development server (port 5173)
npm run build     # Type-check and build for production
npm run preview   # Preview production build locally
npm run lint      # Run ESLint
```

### Backend

```bash
sam build         # Build Lambda packages
sam deploy        # Deploy to AWS
sam local invoke  # Test Lambda locally
python -m pytest  # Run tests
```

---

## API Reference

### WebSocket Actions (send via `action` field)

| Action | Description |
|--------|-------------|
| `sendMessage` | Send a text message to the AI |
| `voice_start` | Begin a voice recording session |
| `audio_chunk` | Send a base64-encoded PCM audio chunk |
| `voice_stop` | End voice session, trigger AI processing |
| `restore_session` | Restore a previous conversation |
| `analyze_repo` | Analyze a GitHub repository |

### REST Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/auth/signup` | Create account (email + password) |
| `POST` | `/auth/login` | Login, returns JWT |
| `GET` | `/auth/me` | Verify token, get user info |
| `POST` | `/upload` | Get presigned URL for file upload |
| `POST` | `/export` | Export diagram as PNG/SVG |

---

## Nova 2 Model Reference

| Model | ID | Use Case |
|-------|----|----------|
| Nova 2 Lite | `us.amazon.nova-2-lite-v1:0` | Text generation, diagram creation, intent classification |
| Nova 2 Sonic | `amazon.nova-2-sonic-v1:0` | Bidirectional voice streaming (STT + TTS) |

> **Note:** There is no "Nova 2 Pro" model. Nova 2 only ships with Lite and Sonic variants.

---

## License

This project is for demonstration and educational purposes.
