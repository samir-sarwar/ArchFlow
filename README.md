# ArchFlow

**Design systems by conversation.**

ArchFlow is a voice-first AI application that enables software architects and developers to design system architecture diagrams through natural conversation. Powered by Amazon Nova on AWS Bedrock.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
sam build
sam local start-api
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Architecture

- **Backend**: Python 3.12, AWS Lambda, SAM, Amazon Bedrock (Nova models)
- **Frontend**: React 18, TypeScript, Vite, Mermaid.js, Zustand, Tailwind CSS

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for details.
