# 03 - Code Organization & Best Practices

**Prerequisites:** Read `01-PROJECT-OVERVIEW.md` and `02-TECH-STACK.md` first

---

## 1. Repository Structure

```
ArchFlow/
├── backend/
│   ├── src/
│   │   ├── agents/                 # Multi-agent system
│   │   │   ├── __init__.py
│   │   │   ├── orchestrator.py     # Main conversation router
│   │   │   ├── requirements_analyst.py
│   │   │   ├── architecture_advisor.py
│   │   │   ├── diagram_generator.py
│   │   │   └── context_analyzer.py
│   │   │
│   │   ├── services/               # Business logic services
│   │   │   ├── __init__.py
│   │   │   ├── bedrock_client.py   # Bedrock API wrapper
│   │   │   ├── voice_handler.py    # Audio stream processing
│   │   │   ├── diagram_validator.py
│   │   │   ├── state_manager.py    # DynamoDB operations
│   │   │   └── file_processor.py   # S3/Textract integration
│   │   │
│   │   ├── handlers/               # Lambda entry points
│   │   │   ├── __init__.py
│   │   │   ├── websocket.py        # WebSocket $connect, $disconnect
│   │   │   ├── voice_stream.py     # Voice streaming endpoint
│   │   │   ├── file_upload.py      # File upload handler
│   │   │   └── export.py           # Export diagram handler
│   │   │
│   │   ├── models/                 # Pydantic data models
│   │   │   ├── __init__.py
│   │   │   ├── conversation.py
│   │   │   ├── diagram.py
│   │   │   └── agent_response.py
│   │   │
│   │   └── utils/                  # Shared utilities
│   │       ├── __init__.py
│   │       ├── logger.py           # Structured logging
│   │       ├── errors.py           # Custom exceptions
│   │       └── validators.py       # Input validation
│   │
│   ├── tests/
│   │   ├── unit/
│   │   │   ├── test_agents/
│   │   │   ├── test_services/
│   │   │   └── test_utils/
│   │   └── integration/
│   │       ├── test_voice_flow.py
│   │       └── test_file_upload.py
│   │
│   ├── template.yaml               # SAM template (IaC)
│   ├── requirements.txt            # Python dependencies
│   ├── samconfig.toml             # SAM configuration
│   └── README.md
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── VoiceInterface/
│   │   │   │   ├── VoiceRecorder.tsx
│   │   │   │   ├── AudioVisualizer.tsx
│   │   │   │   ├── ConversationDisplay.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── DiagramCanvas/
│   │   │   │   ├── MermaidRenderer.tsx
│   │   │   │   ├── DiagramControls.tsx
│   │   │   │   ├── ExportMenu.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── ManualEditor/
│   │   │   │   ├── Canvas.tsx
│   │   │   │   ├── ElementLibrary.tsx
│   │   │   │   ├── NodeComponent.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   ├── FileUpload/
│   │   │   │   ├── Dropzone.tsx
│   │   │   │   ├── FileList.tsx
│   │   │   │   └── index.ts
│   │   │   │
│   │   │   └── shared/
│   │   │       ├── Button.tsx
│   │   │       ├── Modal.tsx
│   │   │       ├── Toast.tsx
│   │   │       └── LoadingSpinner.tsx
│   │   │
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   ├── useVoiceRecording.ts
│   │   │   ├── useDiagramState.ts
│   │   │   ├── useFileUpload.ts
│   │   │   └── useConversation.ts
│   │   │
│   │   ├── stores/
│   │   │   ├── conversationStore.ts
│   │   │   ├── diagramStore.ts
│   │   │   └── uiStore.ts
│   │   │
│   │   ├── services/
│   │   │   ├── websocket.ts
│   │   │   ├── api.ts
│   │   │   └── audio.ts
│   │   │
│   │   ├── types/
│   │   │   ├── conversation.ts
│   │   │   ├── diagram.ts
│   │   │   ├── api.ts
│   │   │   └── index.ts
│   │   │
│   │   ├── utils/
│   │   │   ├── formatDate.ts
│   │   │   ├── downloadFile.ts
│   │   │   └── validateMermaid.ts
│   │   │
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   │
│   ├── public/
│   │   ├── favicon.ico
│   │   └── robots.txt
│   │
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── .env.example
│   └── README.md
│
├── docs/
│   ├── API.md                      # API documentation
│   ├── ARCHITECTURE.md
│   ├── DEPLOYMENT.md
│   └── CONTRIBUTING.md
│
├── .github/
│   └── workflows/
│       └── deploy.yml              # CI/CD (optional)
│
├── .gitignore
├── README.md
└── LICENSE
```

---

## 2. File Naming Conventions

### 2.1 Python (Backend)

**Files:** `snake_case.py`
```python
# Good
orchestrator.py
bedrock_client.py
state_manager.py

# Bad
Orchestrator.py
bedrockClient.py
StateManager.py
```

**Classes:** `PascalCase`
```python
class OrchestratorAgent:
    pass

class BedrockClient:
    pass
```

**Functions/Variables:** `snake_case`
```python
def process_voice_input(audio_chunk: bytes):
    session_id = generate_session_id()
    return response
```

**Constants:** `SCREAMING_SNAKE_CASE`
```python
MAX_CONVERSATION_MESSAGES = 100
DEFAULT_TIMEOUT = 60
BEDROCK_MODEL_SONIC = "us.amazon.nova-sonic-v2:0"
```

### 2.2 TypeScript (Frontend)

**Components:** `PascalCase.tsx`
```typescript
// Good
VoiceRecorder.tsx
MermaidRenderer.tsx
ConversationDisplay.tsx

// Bad
voice-recorder.tsx
mermaidRenderer.tsx
conversation_display.tsx
```

**Hooks:** `useCamelCase.ts`
```typescript
// Good
useWebSocket.ts
useVoiceRecording.ts

// Bad
UseWebSocket.ts
use-voice-recording.ts
```

**Utilities:** `camelCase.ts`
```typescript
// Good
formatDate.ts
downloadFile.ts

// Bad
FormatDate.ts
download_file.ts
```

**Types/Interfaces:** `PascalCase`
```typescript
interface ConversationMessage {
    role: 'user' | 'assistant';
    content: string;
}

type DiagramType = 'flowchart' | 'sequence' | 'er' | 'c4';
```

---

## 3. Code Quality Standards

### 3.1 Python Backend

**Type Hints (Required):**
```python
from typing import List, Dict, Optional
from pydantic import BaseModel

def process_message(
    message: str,
    session_id: str,
    context: Optional[Dict] = None
) -> Dict[str, any]:
    """
    Process user message and return AI response.
    
    Args:
        message: User input message
        session_id: Unique session identifier
        context: Optional conversation context
    
    Returns:
        Dict containing response text and diagram update
    
    Raises:
        SessionExpiredError: If session has timed out
        BedrockThrottlingError: If API rate limit hit
    """
    pass
```

**Docstrings (Google Style):**
```python
class ArchitectureAdvisor:
    """
    Agent that provides architecture advice using Nova Pro.
    
    This agent acts as a senior systems architect, suggesting
    design patterns, challenging assumptions, and referencing
    the AWS Well-Architected Framework.
    
    Attributes:
        bedrock_client: Client for calling Bedrock API
        system_prompt: Persona definition for the agent
    
    Example:
        advisor = ArchitectureAdvisor()
        response = await advisor.suggest(context)
    """
    
    def __init__(self):
        """Initialize the architecture advisor agent."""
        self.bedrock_client = BedrockClient()
        self.system_prompt = SENIOR_ARCHITECT_PROMPT
    
    async def suggest(self, context: ConversationContext) -> AgentResponse:
        """
        Generate architecture suggestions.
        
        Args:
            context: Current conversation context including requirements
        
        Returns:
            AgentResponse with architecture suggestions and rationale
        """
        pass
```

**Error Handling:**
```python
# Good - Specific exceptions, proper logging
from utils.errors import SessionExpiredError, BedrockThrottlingError
from utils.logger import logger

async def get_session(session_id: str) -> ConversationContext:
    try:
        response = dynamodb.get_item(Key={'session_id': session_id})
    except ClientError as e:
        logger.error(f"DynamoDB error: {e}", extra={'session_id': session_id})
        raise SessionExpiredError(f"Session {session_id} not found")
    
    if 'Item' not in response:
        raise SessionExpiredError(f"Session {session_id} not found")
    
    return ConversationContext(**response['Item'])

# Bad - Generic exceptions, silent failures
def get_session(session_id):
    try:
        response = dynamodb.get_item(Key={'session_id': session_id})
        return response['Item']
    except:
        return None
```

**Logging:**
```python
from utils.logger import logger

# Good - Structured logging with context
logger.info(
    "Processing voice input",
    extra={
        'session_id': session_id,
        'audio_duration_ms': duration,
        'agent': 'orchestrator'
    }
)

logger.error(
    "Bedrock API call failed",
    exc_info=True,
    extra={
        'model_id': model_id,
        'session_id': session_id
    }
)

# Bad - Unstructured logging, missing context
print("Processing voice")
logger.error("API failed")
```

### 3.2 TypeScript Frontend

**Strict Type Safety:**
```typescript
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "strictNullChecks": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true
  }
}

// Good - Explicit types, no 'any'
interface VoiceRecorderProps {
  onAudioChunk: (chunk: ArrayBuffer) => void;
  isRecording: boolean;
  onError: (error: Error) => void;
}

export function VoiceRecorder({ 
  onAudioChunk, 
  isRecording, 
  onError 
}: VoiceRecorderProps) {
  const [audioLevel, setAudioLevel] = useState<number>(0);
  
  const handleDataAvailable = useCallback((event: BlobEvent) => {
    event.data.arrayBuffer().then(onAudioChunk);
  }, [onAudioChunk]);
  
  return <div>...</div>;
}

// Bad - Implicit types, 'any' usage
export function VoiceRecorder(props: any) {
  const [audioLevel, setAudioLevel] = useState(0);
  
  const handleDataAvailable = (event) => {
    props.onAudioChunk(event.data);
  };
  
  return <div>...</div>;
}
```

**Component Structure:**
```typescript
// Good - Functional component with hooks, proper exports
import { useState, useEffect, useCallback } from 'react';
import type { DiagramSyntax } from '@/types/diagram';

interface MermaidRendererProps {
  syntax: DiagramSyntax;
  onRenderComplete?: () => void;
  onError?: (error: Error) => void;
}

export function MermaidRenderer({
  syntax,
  onRenderComplete,
  onError
}: MermaidRendererProps) {
  const [svg, setSvg] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  
  const renderDiagram = useCallback(async () => {
    setIsLoading(true);
    try {
      const result = await mermaid.render('diagram', syntax);
      setSvg(result.svg);
      onRenderComplete?.();
    } catch (error) {
      onError?.(error as Error);
    } finally {
      setIsLoading(false);
    }
  }, [syntax, onRenderComplete, onError]);
  
  useEffect(() => {
    renderDiagram();
  }, [renderDiagram]);
  
  if (isLoading) return <LoadingSpinner />;
  
  return (
    <div 
      className="diagram-container"
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}
```

**Error Handling:**
```typescript
// Good - Typed errors, proper error boundaries
try {
  const response = await api.uploadFile(file);
  onSuccess(response);
} catch (error) {
  if (error instanceof NetworkError) {
    showToast('Network error. Please check your connection.', 'error');
  } else if (error instanceof ValidationError) {
    showToast(error.message, 'warning');
  } else {
    showToast('An unexpected error occurred.', 'error');
    logger.error('File upload failed', { error });
  }
}

// Bad - Generic error handling
try {
  await api.uploadFile(file);
} catch (e) {
  alert('Error!');
}
```

---

## 4. Design Patterns

### 4.1 Backend Patterns

**Dependency Injection:**
```python
# Good - Testable, dependencies injected
class OrchestratorAgent:
    def __init__(
        self,
        bedrock_client: BedrockClient,
        state_manager: StateManager,
        agents: Dict[str, Agent]
    ):
        self.bedrock = bedrock_client
        self.state = state_manager
        self.agents = agents

# Usage
orchestrator = OrchestratorAgent(
    bedrock_client=BedrockClient(),
    state_manager=StateManager(),
    agents={
        'requirements': RequirementsAnalyst(),
        'advisor': ArchitectureAdvisor()
    }
)

# Bad - Hard to test, tight coupling
class OrchestratorAgent:
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime')
        self.dynamodb = boto3.resource('dynamodb').Table('conversations')
```

**Repository Pattern (State Management):**
```python
class ConversationRepository:
    """Abstract conversation storage operations."""
    
    async def get(self, session_id: str) -> ConversationContext:
        """Retrieve conversation by session ID."""
        raise NotImplementedError
    
    async def save(self, context: ConversationContext) -> None:
        """Save conversation context."""
        raise NotImplementedError
    
    async def delete(self, session_id: str) -> None:
        """Delete conversation."""
        raise NotImplementedError

class DynamoDBConversationRepository(ConversationRepository):
    """DynamoDB implementation of conversation storage."""
    
    def __init__(self, table_name: str):
        self.table = dynamodb.Table(table_name)
    
    async def get(self, session_id: str) -> ConversationContext:
        response = self.table.get_item(Key={'session_id': session_id})
        if 'Item' not in response:
            raise SessionNotFoundError(f"Session {session_id} not found")
        return ConversationContext(**response['Item'])
    
    async def save(self, context: ConversationContext) -> None:
        self.table.put_item(Item=context.dict())
```

**Strategy Pattern (Agent Selection):**
```python
from abc import ABC, abstractmethod

class Agent(ABC):
    """Base agent interface."""
    
    @abstractmethod
    async def process(self, context: ConversationContext) -> AgentResponse:
        """Process conversation and return response."""
        pass

class RequirementsAnalyst(Agent):
    async def process(self, context: ConversationContext) -> AgentResponse:
        # Requirements analysis logic
        pass

class ArchitectureAdvisor(Agent):
    async def process(self, context: ConversationContext) -> AgentResponse:
        # Architecture advice logic
        pass

# Orchestrator selects strategy based on intent
class OrchestratorAgent:
    def select_agent(self, intent: str) -> Agent:
        strategies = {
            'clarification': self.agents['requirements'],
            'advice': self.agents['advisor'],
            'diagram': self.agents['generator']
        }
        return strategies.get(intent, self.agents['advisor'])
```

### 4.2 Frontend Patterns

**Custom Hooks:**
```typescript
// Good - Reusable logic in custom hook
export function useWebSocket(url: string) {
  const [ws, setWs] = useState<WebSocket | null>(null);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<MessageEvent | null>(null);
  
  useEffect(() => {
    const websocket = new WebSocket(url);
    
    websocket.onopen = () => setIsConnected(true);
    websocket.onclose = () => setIsConnected(false);
    websocket.onmessage = (event) => setLastMessage(event);
    
    setWs(websocket);
    
    return () => {
      websocket.close();
    };
  }, [url]);
  
  const sendMessage = useCallback((message: any) => {
    if (ws && isConnected) {
      ws.send(JSON.stringify(message));
    }
  }, [ws, isConnected]);
  
  return { isConnected, lastMessage, sendMessage };
}

// Usage
function VoiceInterface() {
  const { isConnected, lastMessage, sendMessage } = useWebSocket(WS_URL);
  
  useEffect(() => {
    if (lastMessage) {
      handleAIResponse(JSON.parse(lastMessage.data));
    }
  }, [lastMessage]);
  
  return <div>...</div>;
}
```

**Compound Components:**
```typescript
// Good - Flexible, composable components
export function DiagramCanvas({ children }: PropsWithChildren) {
  return (
    <div className="diagram-canvas">
      {children}
    </div>
  );
}

DiagramCanvas.Renderer = MermaidRenderer;
DiagramCanvas.Controls = DiagramControls;
DiagramCanvas.Export = ExportMenu;

// Usage
<DiagramCanvas>
  <DiagramCanvas.Renderer syntax={syntax} />
  <DiagramCanvas.Controls onZoomIn={handleZoom} />
  <DiagramCanvas.Export onExport={handleExport} />
</DiagramCanvas>
```

---

## 5. Testing Strategy

### 5.1 Backend Testing

**Unit Tests (pytest):**
```python
# tests/unit/test_agents/test_orchestrator.py
import pytest
from src.agents.orchestrator import OrchestratorAgent
from src.models.conversation import ConversationContext

@pytest.fixture
def mock_bedrock_client(mocker):
    return mocker.Mock()

@pytest.fixture
def orchestrator(mock_bedrock_client):
    return OrchestratorAgent(
        bedrock_client=mock_bedrock_client,
        state_manager=mocker.Mock(),
        agents={}
    )

def test_analyze_intent_clarification(orchestrator):
    context = ConversationContext(
        session_id='test-123',
        messages=[],
        requirements={}
    )
    
    intent = await orchestrator.analyze_intent(
        "What database should I use?",
        context
    )
    
    assert intent.type == 'clarification_needed'
    assert 'database' in intent.entities

def test_route_to_advisor(orchestrator, mocker):
    mock_advisor = mocker.Mock()
    orchestrator.agents['advisor'] = mock_advisor
    
    await orchestrator.route_request("Should I use microservices?", context)
    
    mock_advisor.process.assert_called_once()
```

**Integration Tests:**
```python
# tests/integration/test_voice_flow.py
import pytest
from moto import mock_dynamodb, mock_s3

@pytest.fixture
def aws_setup():
    with mock_dynamodb(), mock_s3():
        # Create test DynamoDB table
        dynamodb = boto3.resource('dynamodb')
        table = dynamodb.create_table(
            TableName='test-conversations',
            KeySchema=[{'AttributeName': 'session_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'session_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        yield table

def test_end_to_end_voice_flow(aws_setup):
    # Test complete flow: voice input → orchestrator → agent → diagram
    pass
```

### 5.2 Frontend Testing

**Component Tests (Vitest + Testing Library):**
```typescript
import { render, screen, fireEvent } from '@testing-library/react';
import { VoiceRecorder } from './VoiceRecorder';

describe('VoiceRecorder', () => {
  it('requests microphone access on start recording', async () => {
    const mockGetUserMedia = vi.fn().mockResolvedValue({
      getTracks: () => []
    });
    global.navigator.mediaDevices.getUserMedia = mockGetUserMedia;
    
    const { getByRole } = render(
      <VoiceRecorder onAudioChunk={vi.fn()} />
    );
    
    const startButton = getByRole('button', { name: /start/i });
    fireEvent.click(startButton);
    
    await waitFor(() => {
      expect(mockGetUserMedia).toHaveBeenCalledWith({ audio: true });
    });
  });
});
```

---

