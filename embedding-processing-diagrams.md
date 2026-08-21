# Embedding Processing Diagrams

This document describes the current processing flow across `server/embed.py`,
`server/chunker.py`, and `server/database/chroma.py`.

## Sequence diagram

```mermaid
sequenceDiagram
    actor User
    participant E as embed.py<br/>embedding()
    participant FS as Local policy folder
    participant C as chunker.py<br/>chunker()
    participant O as openai_client.py<br/>openai_chunker()
    participant M as OpenAI chat model
    participant V as chroma.py<br/>embed()
    participant S as chroma.py<br/>VectorStore
    participant DB as ChromaDB

    User->>E: embedding(directory_path)
    E->>FS: List .md files
    loop Each Markdown file
        E->>C: chunker(directory_path, filename)
        C->>FS: Read file content
        C->>O: openai_chunker(filename, content)
        O->>M: Request structured semantic chunks
        M-->>O: section, subsection, content
        O-->>C: Chunks with document_id and filename
        C-->>E: Chunk list
    end

    E->>S: VectorStore()
    S->>DB: Open persistent `documents` collection
    loop Each generated chunk
        E->>V: embed(chunk content)
        V-->>E: 384-dimension vector
        E->>S: save_vector(vector, content, metadata, document_id)
        S->>DB: Add ID, embedding, document, and metadata
    end
    DB-->>S: Persisted vectors
    S-->>E: Saved document IDs
```

## Component diagram

```mermaid
flowchart LR
    Folder[Local policy folder\nMarkdown files] --> Embed

    subgraph Ingestion[Ingestion pipeline]
        Embed[embed.py\nembedding()] --> Chunker[chunker.py\nchunker()]
        Chunker --> OpenAIClient[openai_client.py\nopenai_chunker()]
        OpenAIClient --> LLM[OpenAI chat model]
        LLM -->|structured chunks| OpenAIClient
        OpenAIClient -->|document_id, filename, section, subsection, content| Chunker
        Chunker -->|chunks| Embed
        Embed --> Encoder[chroma.py\nembed()]
        Encoder -->|384-dimension embedding| Store[chroma.py\nVectorStore.save_vector()]
    end

    Store --> Chroma[(ChromaDB\ndocuments collection)]

    subgraph Retrieval[Query path]
        Query[Search text] --> Encoder
        Encoder -->|query vector| Search[chroma.py\nVectorStore.search_vector()]
        Search --> Chroma
        Chroma -->|IDs, chunk text, metadata, distances| Search
        Search --> Results[Ranked search results]
    end
```

## Stored record fields

For every saved chunk, Chroma receives:

| Field | Source |
| --- | --- |
| `id` | `chunk["document_id"]` |
| `embedding` | `embed(chunk["content"])` |
| `document` | `chunk["content"]` |
| metadata `title` | `chunk["filename"]` |
| metadata `section` | `chunk["section"]` |

`openai_chunker()` also creates a `subsection`, but the current `embed.py`
implementation does not include it in the metadata passed to `save_vector()`.

> Current behavior: `chunks` is reassigned for each file in `embedding()`, so
> after the file loop only the chunks from the final Markdown file are saved.
