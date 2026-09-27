# Architecture Diagrams

These diagrams describe the current application flow and component boundaries.

## Chat Request Sequence

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser UI
    participant API as FastAPI server
    participant DB as SQLite database
    participant RAG as RAG query service
    participant Embedder as Sentence Transformer
    participant Chroma as ChromaDB
    participant OpenAI as OpenAI Chat API

    User->>UI: Enter message
    UI->>API: POST /chat(message, user_id, session_id?)

    alt New chat session
        API->>DB: Validate user
        DB-->>API: User
        API->>DB: Create chat session
        DB-->>API: Session
    else Existing chat session
        API->>DB: Load session and messages
        DB-->>API: Session and history
    end

    API->>RAG: Retrieve policy context(message)
    RAG->>Embedder: Embed user query
    Embedder-->>RAG: Query vector
    RAG->>Chroma: Semantic search(top 5 chunks)
    Chroma-->>RAG: Documents, metadata, distances
    RAG-->>API: Formatted policy context

    API->>OpenAI: Send message, history, compaction summary, and RAG context
    OpenAI-->>API: Assistant response
    API->>DB: Save user message
    API->>DB: Save assistant message
    API->>DB: Recalculate session size
    DB-->>API: Updated size
    API-->>UI: Response and session id
    UI-->>User: Render assistant response
```

## Chat Request Flow

```mermaid
flowchart TD
    A([User submits message]) --> B{session_id provided?}

    B -- No --> C{user_id valid?}
    C -- No --> E([Return HTTP 400/404])
    C -- Yes --> D[Create new chat session]
    D --> F{Message is empty?}
    F -- Yes --> G([Return session id])
    F -- No --> H[Retrieve policy context from RAG]

    B -- Yes --> I{Session exists?}
    I -- No --> E
    I -- Yes --> J{Message is empty?}
    J -- Yes --> E
    J -- No --> H

    H --> K[Embed query]
    K --> L[Search ChromaDB]
    L --> M[Build formatted policy context]
    M --> N{Latest compaction exists?}

    N -- Yes --> O[Load messages after compaction and summary]
    N -- No --> P[Load complete session history]
    O --> Q[Call OpenAI chat API]
    P --> Q
    Q --> R[Save user and assistant messages]
    R --> S[Recalculate session size]
    S --> T{Size exceeds 1000?}
    T -- Yes --> U([Return compression prompt])
    T -- No --> V([Return assistant response])

    W([User requests /compact]) --> X[Load session messages]
    X --> Y[Summarize with OpenAI]
    Y --> Z[Upsert compaction record]
    Z --> AA[Update post-compaction size]
    AA --> AB([Return compacted summary])
```

## Component Diagram

```mermaid
flowchart LR
    Browser[Browser UI\nserver/templates/chat.html]
    API[FastAPI application\nserver/server.py]
    Client[OpenAI client\nserver/openai_client.py]
    DBRepo[Database repository\nserver/database/db.py]
    Models[SQLModel entities\nUser, ChatSession, ChatMessage, ChatCompaction]
    SQLite[(SQLite\ndata/database.db)]
    RAGQuery[RAG query\nrag/query.py]
    Embedder[Embedding model\nall-MiniLM-L6-v2]
    ChromaRepo[ChromaDB helpers\nrag/chromadb.py]
    Chroma[(Persistent ChromaDB\ndata/chroma_data)]
    Ingest[Policy ingestion script\nrag/chroma.py]
    Policies[(Policy Markdown files\ndata/policies)]
    OpenAI[(OpenAI API\nchat completions)]

    Browser -->|HTTP| API
    API --> Client
    API --> DBRepo
    API --> RAGQuery
    DBRepo --> Models
    DBRepo --> SQLite
    RAGQuery --> Embedder
    RAGQuery --> ChromaRepo
    ChromaRepo --> Chroma
    Client --> OpenAI

    Policies --> Ingest
    Ingest --> Client
    Ingest --> Embedder
    Ingest --> ChromaRepo
```

The `/compact` endpoint uses the same OpenAI client and database repository but does not perform a RAG search. Policy ingestion is a separate preparation step that chunks documents with OpenAI, embeds them locally, and stores the vectors in ChromaDB.