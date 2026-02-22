# 02 - Technical Stack & Architecture

**Prerequisites:** Read `01-PROJECT-OVERVIEW.md` first

---

## 1. System Architecture Overview

```
┌──────────────────────────────────────────────────────────────┐
│                        Frontend (React)                      │
│  ┌────────────┐  ┌────────────┐  ┌──────────────────────┐  │
│  │   Voice    │  │  Diagram   │  │   File Upload /      │  │
│  │ Interface  │  │  Canvas    │  │   Manual Editor      │  │
│  └─────┬──────┘  └──────┬─────┘  └───────────┬──────────┘  │
└────────┼─────────────────┼───────────────────┼──────────────┘
         │                 │                   │
         │ WebSocket       │ WebSocket         │ REST API
         │                 │                   │
┌────────▼─────────────────▼───────────────────▼──────────────┐
│              Amazon API Gateway                              │
│  ┌──────────────────────┐  ┌──────────────────────────────┐ │
│  │  WebSocket Routes    │  │     REST Routes              │ │
│  └──────────┬───────────┘  └────────────┬─────────────────┘ │
└─────────────┼──────────────────────────┼────────────────────┘
              │                           │
    ┌─────────▼────────┐        ┌────────▼─────────┐
    │  Voice Stream    │        │  File Upload     │
    │  Lambda          │        │  Lambda          │
    └─────────┬────────┘        └────────┬─────────┘
              │                           │
    ┌─────────▼─────────────────────────┬─┘
    │   Orchestrator Lambda             │
    │   (Routes to Agents)              │
    └─────────┬─────────────────────────┘
              │
       ┌──────┴──────┬──────────┬───────────┐
       │             │          │           │
  ┌────▼─────┐ ┌────▼─────┐  ┌─▼──────┐ ┌─▼────────┐
  │Requirements│Architecture│Diagram  │ │ Context  │
  │  Analyst  │  Advisor   │Generator│ │ Analyzer │
  │(Nova Lite)│(Nova Pro)  │(Lite)   │ │(Embeddings)
  └────┬──────┘ └────┬─────┘  └─┬─────┘ └─┬────────┘
       │             │           │         │
       └─────────────┴───────────┴─────────┘
                     │
            ┌────────▼─────────┐
            │  Amazon Bedrock  │
            │  (Nova Models)   │
            └──────────────────┘

┌──────────────────────────────────────────────────────────────┐
│                    Data Layer                                │
│  ┌──────────┐  ┌──────────┐  ┌────────────────────────────┐ │
│  │DynamoDB  │  │   S3     │  │      CloudWatch           │ │
│  │(State)   │  │ (Files)  │  │  (Logs & Metrics)         │ │
│  └──────────┘  └──────────┘  └────────────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

---

## 2. Backend Stack

### 2.1 Runtime & Framework

**Language:** Python 3.12
- **Why:** Best AWS SDK support for Bedrock/Nova, extensive AI/ML libraries
- **Alternatives Considered:** 
  - Node.js: Less mature Bedrock SDK
  - Go: Sparse Nova examples, slower development

**Framework:** AWS Lambda (Serverless Functions)
- **Why:** No server management, auto-scaling, pay-per-request
- **Configuration:**
  - Memory: 1024MB-2048MB (tuned per function)
  - Timeout: 60 seconds (voice/diagram), 300 seconds (file processing)
  - Concurrency limit: 100 (cost control)

**Deployment:** AWS SAM (Serverless Application Model)
- **Why:** Infrastructure as Code, local testing, easy deployment
- **Alternative:** AWS CDK (more complex, overkill for hackathon)

**API Layer:**
- **WebSocket:** Real-time voice streaming, diagram updates
- **REST API:** File uploads, exports, session management
- **Gateway:** Amazon API Gateway (both WebSocket and HTTP APIs)

### 2.2 AWS AI/ML Services

**Primary: Amazon Bedrock**
- **Purpose:** Access to Nova foundation models
- **Models Used:**
  
  1. **Nova 2 Sonic** (`us.amazon.nova-sonic-v2:0`)
     - **Use:** Real-time voice conversation
     - **Features:** Voice-to-text, conversational AI, low latency
     - **Calls:** Every voice input/output
  
  2. **Nova Pro** (`us.amazon.nova-pro-v1:0`)
     - **Use:** Complex reasoning, architecture advice
     - **Features:** Deep analysis, multi-step reasoning
     - **Calls:** Architecture Advisor agent, Orchestrator decisions
  
  3. **Nova Lite** (`us.amazon.nova-lite-v1:0`)
     - **Use:** Quick tasks, diagram generation
     - **Features:** Fast responses, lightweight tasks
     - **Calls:** Requirements questions, Mermaid syntax generation
  
  4. **Nova Multimodal Embeddings**
     - **Use:** Document/image understanding
     - **Features:** Semantic search, context extraction
     - **Calls:** File uploads, context analysis

**Supporting Services:**

- **Amazon Transcribe** (Fallback)
  - **Use:** If Nova 2 Sonic unavailable or fails
  - **Features:** Streaming speech-to-text, custom vocabulary

- **Amazon Polly** (Voice Synthesis)
  - **Use:** Text-to-speech for AI responses
  - **Voice:** Neural (Joanna/Matthew for natural sound)

- **Amazon Textract**
  - **Use:** Extract text from PDF/image uploads
  - **Features:** OCR, layout analysis, table extraction

### 2.3 Data Storage

**Amazon DynamoDB**
- **Purpose:** Conversation state, session management
- **Billing:** On-demand (handles traffic spikes)
- **Tables:**

  ```
  ConversationsTable
  ├── Partition Key: session_id (String)
  ├── Attributes:
  │   ├── created_at (String, ISO 8601)
  │   ├── last_activity (String, ISO 8601)
  │   ├── messages (List, conversation history)
  │   ├── current_diagram (String, Mermaid syntax)
  │   ├── diagram_versions (List, version history)
  │   ├── uploaded_files (List, S3 keys)
  │   └── metadata (Map, requirements, decisions)
  └── GSI: user_id-index (for multi-session support)
  ```

**Amazon S3**
- **Purpose:** File storage (uploads, exports, diagram images)
- **Buckets:**
  - `ArchFlow-uploads-{env}`: User uploaded files (PDFs, images)
  - `ArchFlow-exports-{env}`: Generated diagram exports
- **Lifecycle:** Delete files >7 days old (cost optimization)
- **Access:** Presigned URLs (1-hour expiry, security)

**Amazon CloudWatch**
- **Purpose:** Logs, metrics, alarms
- **Log Groups:**
  - `/aws/lambda/ArchFlow-orchestrator`
  - `/aws/lambda/ArchFlow-voice-stream`
  - `/aws/lambda/ArchFlow-file-processor`
- **Metrics:** Custom metrics for conversation_started, diagram_generated, errors
- **Alarms:** Error rate >5%, p95 latency >5s

### 2.4 Async Processing

**Amazon SQS** (Simple Queue Service)
- **Purpose:** Decouple file processing, handle bursts
- **Queues:**
  - `ArchFlow-file-processing-queue`: Async document analysis
  - `ArchFlow-diagram-export-queue`: Background PNG/SVG generation
- **Configuration:** 
  - Visibility timeout: 300 seconds
  - Dead letter queue: After 3 retries

**Amazon EventBridge** (Optional)
- **Purpose:** Scheduled tasks (session cleanup)
- **Rules:**
  - Daily: Delete expired sessions (>7 days)
  - Hourly: Generate CloudWatch dashboard snapshots

### 2.5 Python Dependencies

```python
# requirements.txt

# AWS SDK
boto3>=1.34.0              # AWS service clients
botocore>=1.34.0           # Low-level AWS API

# Data Validation
pydantic>=2.5.0            # Type validation, data models

# Logging
python-json-logger>=2.0    # Structured JSON logging

# Diagram Validation
mermaid-py>=0.3.0          # Mermaid syntax validation

# Utilities
python-dateutil>=2.8       # Date/time parsing
uuid>=1.30                 # Session ID generation

# Testing
pytest>=7.4.0              # Unit testing
moto>=4.2.0                # Mock AWS services
pytest-asyncio>=0.21.0     # Async test support
```

---

## 3. Frontend Stack

### 3.1 Framework & Libraries

**Framework:** React 18+ with TypeScript
- **Why:** Component-based, strong ecosystem, type safety
- **Build Tool:** Vite (fast HMR, optimized builds)

**Key Libraries:**

```json
{
  "dependencies": {
    "react": "^18.2.0",
    "react-dom": "^18.2.0",
    
    "mermaid": "^10.6.0",              // Diagram rendering
    "react-dnd": "^16.0.1",            // Drag-and-drop for manual mode
    "react-dropzone": "^14.2.3",       // File uploads
    
    "zustand": "^4.4.7",               // State management (lightweight)
    
    "tailwindcss": "^3.4.0",           // Styling
    "@radix-ui/react-dialog": "^1.0.5",
    "@radix-ui/react-dropdown-menu": "^2.0.6",
    
    "lucide-react": "^0.300.0",        // Icons
    
    "date-fns": "^2.30.0"              // Date formatting
  },
  "devDependencies": {
    "@types/react": "^18.2.0",
    "@types/react-dom": "^18.2.0",
    "@vitejs/plugin-react": "^4.2.0",
    "typescript": "^5.3.0",
    "vite": "^5.0.0",
    "eslint": "^8.55.0",
    "prettier": "^3.1.0"
  }
}
```

### 3.2 Voice Interface

**Web Audio API**
- **Purpose:** Capture microphone input
- **Configuration:**
  - Sample Rate: 16kHz (optimized for speech)
  - Channels: 1 (mono)
  - Bit Depth: 16-bit PCM

**MediaRecorder API**
- **Purpose:** Stream audio chunks to backend
- **Configuration:**
  - Chunk size: 500ms (low latency)
  - Format: `audio/webm;codecs=opus` or `audio/wav`

**WebSocket (Native)**
- **Purpose:** Real-time bidirectional communication
- **Protocol:** `wss://` (secure WebSocket)
- **Message Format:**
  ```typescript
  {
    type: 'audio_chunk' | 'transcription' | 'ai_response',
    sessionId: string,
    payload: {
      audio?: ArrayBuffer,
      text?: string,
      diagram?: string
    }
  }
  ```

### 3.3 Diagram Rendering

**Mermaid.js 10+**
- **Features:** Client-side diagram generation
- **Supported Types:**
  - Flowcharts (graph TD, LR, RL, BT)
  - Sequence diagrams
  - Entity-Relationship diagrams
  - C4 diagrams (context, container, component)

**Canvas API** (Manual Mode)
- **Purpose:** Drag-and-drop diagram editor
- **Libraries:** React DnD for interactions
- **Export:** Canvas → PNG/SVG

### 3.4 State Management

**Zustand**
- **Why:** Lightweight (3KB), no boilerplate, TypeScript-first

**Stores:**

```typescript
// conversationStore.ts
interface ConversationStore {
  sessionId: string;
  messages: Message[];
  isRecording: boolean;
  currentTranscript: string;
  addMessage: (message: Message) => void;
  setRecording: (isRecording: boolean) => void;
}

// diagramStore.ts
interface DiagramStore {
  currentSyntax: string;
  history: DiagramVersion[];
  mode: 'voice' | 'manual';
  updateDiagram: (syntax: string) => void;
  undo: () => void;
  redo: () => void;
  switchMode: (mode: 'voice' | 'manual') => void;
}

// uiStore.ts
interface UIStore {
  isLoading: boolean;
  error: Error | null;
  notifications: Notification[];
  setLoading: (loading: boolean) => void;
  setError: (error: Error | null) => void;
  addNotification: (notification: Notification) => void;
}
```

### 3.5 Deployment

**AWS Amplify**
- **Purpose:** Static site hosting, CI/CD
- **Features:** Automatic builds on git push, SSL, CDN
- **Configuration:**
  ```yaml
  version: 1
  frontend:
    phases:
      preBuild:
        commands:
          - npm install
      build:
        commands:
          - npm run build
    artifacts:
      baseDirectory: dist
      files:
        - '**/*'
    cache:
      paths:
        - node_modules/**/*
  ```

**Amazon CloudFront** (CDN)
- **Purpose:** Fast content delivery globally
- **Cache:** Static assets (1 year), API responses (none)

---

## 4. Integration Architecture

### 4.1 Voice Processing Flow

```
User speaks
    ↓
Web Audio API captures audio
    ↓
MediaRecorder creates 500ms chunks
    ↓
WebSocket sends chunk to API Gateway
    ↓
Lambda receives audio chunk
    ↓
Bedrock: Nova 2 Sonic transcribes
    ↓
Orchestrator routes to appropriate agent
    ↓
Agent processes (Nova Pro/Lite)
    ↓
Response generated (text + diagram update)
    ↓
Polly converts text to speech
    ↓
WebSocket sends response back
    ↓
Frontend plays audio + updates diagram
```

**Latency Budget:**
- Audio capture → Backend: 50ms (WebSocket overhead)
- Nova 2 Sonic transcription: 500ms
- Agent processing: 1000ms
- Response generation: 500ms
- Audio synthesis: 300ms
- **Total: ~2.3 seconds** (target <2s, optimize if needed)

### 4.2 File Upload Flow

```
User drops file
    ↓
Frontend uploads to S3 (presigned URL)
    ↓
S3 trigger → Lambda (async)
    ↓
Textract extracts text (PDF/image)
    ↓
Nova embeddings generate vectors
    ↓
Context stored in DynamoDB
    ↓
Notification sent to frontend (WebSocket)
    ↓
"File processed, I found X requirements"
```

### 4.3 Multi-Agent Orchestration

```python
# Orchestrator decision flow

def route_request(user_message, context):
    # 1. Analyze intent using Nova Pro
    intent = analyze_intent(user_message, context)
    
    # 2. Route to appropriate agent(s)
    if intent == 'clarification_needed':
        return requirements_analyst.ask_questions(context)
    
    elif intent == 'architecture_advice':
        return architecture_advisor.suggest(context)
    
    elif intent == 'modify_diagram':
        return diagram_generator.update(user_message, context)
    
    elif intent == 'multi_agent':
        # Parallel execution
        responses = await asyncio.gather(
            architecture_advisor.suggest(context),
            diagram_generator.update(user_message, context)
        )
        return synthesize_responses(responses)
    
    # 3. Update state
    update_conversation_state(response, context)
    
    return response
```

---

## 5. AWS Service Limits & Quotas

### 5.1 Bedrock Quotas

**Nova Model Invocations:**
- Nova 2 Sonic: 100 requests/minute (default)
- Nova Pro: 50 requests/minute
- Nova Lite: 200 requests/minute

**Tokens per Minute:**
- Nova Pro: 100,000 tokens/minute
- Nova Lite: 200,000 tokens/minute

**Mitigation:** Implement exponential backoff, queue requests

### 5.2 Lambda Limits

- **Concurrent executions:** 1000 (default), set to 100 for cost control
- **Memory:** 128MB - 10GB, use 1024-2048MB for performance
- **Timeout:** 900 seconds max, use 60-300s
- **Payload size:** 6MB (synchronous), 256KB (async)

### 5.3 DynamoDB Limits

- **Item size:** 400KB max
- **On-demand throughput:** Automatically scales
- **Partition key:** Max 2048 bytes
- **GSI:** 20 per table

### 5.4 API Gateway Limits

- **WebSocket connections:** 5000 concurrent (default)
- **Message size:** 128KB (WebSocket), 10MB (REST)
- **Timeout:** 30 seconds (REST), 2 hours (WebSocket idle)

---

## 6. Security Architecture

### 6.1 Authentication & Authorization

**API Gateway:**
- IAM authentication for backend-to-backend calls
- API keys for frontend (generated per deployment)
- CORS whitelist: `https://ArchFlow.app` (production domain)

**S3 Presigned URLs:**
- Generate short-lived URLs (1 hour expiry)
- Read-only for uploads, write-only for exports
- No public bucket access

**Lambda Execution Roles:**
```yaml
OrchestratorRole:
  Policies:
    - AmazonBedrockFullAccess
    - DynamoDBCrudPolicy
    - S3ReadWritePolicy
    - CloudWatchLogsPolicy
```

### 6.2 Data Protection

**Encryption:**
- **At Rest:** S3 (SSE-S3), DynamoDB (default encryption)
- **In Transit:** TLS 1.2+ (all API calls, WebSocket)

**PII Handling:**
- No storage of sensitive personal data
- CloudWatch logs: Mask any user-identifiable info
- Conversation content: Stored but anonymized

**Malware Scanning:**
- Lambda trigger on S3 upload
- Scan with ClamAV or AWS partner solution
- Reject infected files before processing

### 6.3 Rate Limiting

**API Gateway:**
- Throttle: 100 requests/second per API key
- Burst: 200 requests

**Application-Level:**
- Max 10 file uploads per session
- Max 100 messages per conversation
- WebSocket: Disconnect if >50 messages/minute

---

## 7. Monitoring & Observability

### 7.1 CloudWatch Metrics

**Custom Metrics:**
```python
cloudwatch.put_metric_data(
    Namespace='ArchFlow',
    MetricData=[
        {
            'MetricName': 'ConversationStarted',
            'Value': 1,
            'Unit': 'Count'
        },
        {
            'MetricName': 'VoiceLatency',
            'Value': latency_ms,
            'Unit': 'Milliseconds'
        },
        {
            'MetricName': 'DiagramGenerated',
            'Value': 1,
            'Unit': 'Count',
            'Dimensions': [
                {'Name': 'DiagramType', 'Value': 'flowchart'}
            ]
        }
    ]
)
```

**Key Metrics to Track:**
- Conversation starts (count)
- Voice response latency (p50, p95, p99)
- Diagram generation time (p50, p95)
- Error rate (percentage)
- Active WebSocket connections (gauge)
- File uploads (count, size distribution)

### 7.2 AWS X-Ray

**Tracing Enabled:**
- All Lambda functions
- Bedrock API calls
- DynamoDB operations

**Trace Example:**
```
User Request → API Gateway → Lambda (Orchestrator)
                                ├─→ Bedrock (Nova Pro)
                                ├─→ DynamoDB (get context)
                                ├─→ Lambda (Architecture Advisor)
                                │   └─→ Bedrock (Nova Pro)
                                └─→ DynamoDB (update state)
```

### 7.3 CloudWatch Alarms

**Critical Alarms:**
- Error rate >5% (5 minutes) → Email notification
- p95 latency >5 seconds → Email notification
- Lambda concurrent executions >80 → Email notification
- DynamoDB throttling events → Email notification

**Billing Alarms:**
- Daily cost >$10 → Email notification
- Monthly forecast >$100 → Email notification

---

## 8. Cost Estimation

### 8.1 Development (11 Days)

**Assumptions:**
- 100 test conversations
- 500 diagram generations
- 50 file uploads
- 1000 Lambda invocations/day

**Estimated Costs:**
- **Bedrock:** $10 (Nova calls)
- **Lambda:** $5 (compute time)
- **DynamoDB:** $2 (on-demand reads/writes)
- **S3:** $1 (storage + requests)
- **API Gateway:** $2 (WebSocket + REST)
- **CloudWatch:** $1 (logs)
- **Total: ~$21 for 11 days**

### 8.2 Demo Day (100 Concurrent Users, 6 Hours)

**Assumptions:**
- 100 users × 3 conversations each = 300 conversations
- 10 messages per conversation = 3000 messages
- 300 diagrams generated

**Estimated Costs:**
- **Bedrock:** $30 (heavy usage)
- **Lambda:** $15 (3000+ invocations)
- **DynamoDB:** $5 (burst traffic)
- **S3:** $2
- **API Gateway:** $5 (WebSocket connections)
- **Total: ~$57 for demo day**

**Combined Budget: <$80 for entire hackathon**

---

## 9. Environment Configuration

### 9.1 Environment Variables

**Backend (Lambda):**
```bash
# AWS Configuration
AWS_REGION=us-east-1

# Bedrock Models
BEDROCK_MODEL_SONIC=us.amazon.nova-sonic-v2:0
BEDROCK_MODEL_PRO=us.amazon.nova-pro-v1:0
BEDROCK_MODEL_LITE=us.amazon.nova-lite-v1:0

# DynamoDB
CONVERSATION_TABLE_NAME=ArchFlow-conversations-${ENV}

# S3
UPLOADS_BUCKET=ArchFlow-uploads-${ENV}
EXPORTS_BUCKET=ArchFlow-exports-${ENV}

# SQS
FILE_PROCESSING_QUEUE_URL=https://sqs.us-east-1.amazonaws.com/.../ArchFlow-file-processing

# Application
LOG_LEVEL=INFO
MAX_CONVERSATION_MESSAGES=100
SESSION_TIMEOUT_MINUTES=30
```

**Frontend (Vite):**
```bash
VITE_WEBSOCKET_URL=wss://abc123.execute-api.us-east-1.amazonaws.com/prod
VITE_API_URL=https://abc123.execute-api.us-east-1.amazonaws.com/prod
VITE_MAX_FILE_SIZE=10485760  # 10MB
VITE_SUPPORTED_AUDIO_FORMATS=audio/webm,audio/wav
```

---

## 10. Next Steps

**After reading this document:**

1. ✅ Understand overall system architecture
2. ✅ Know which AWS services are used and why
3. ✅ Understand data flow (voice, files, diagrams)
4. ✅ Familiar with technology choices

**Next:**
- Read `03-CODE-ORGANIZATION.md` to understand file structure
- Pick a feature file (`04-11`) to implement
- Reference `13-AGENT-PROMPTS.md` when building agent logic
- Use `15-DEPLOYMENT-GUIDE.md` when ready to deploy

**Questions to Answer Before Coding:**
- [ ] Do I have AWS account access?
- [ ] Have I requested Bedrock Nova model access?
- [ ] Do I have SAM CLI installed?
- [ ] Do I understand the voice processing flow?
- [ ] Do I know where each component lives (Lambda vs Frontend)?
