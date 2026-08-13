## assignment date : 25th July
1. my chat application retain hiostoiry of conversations
2. all chat sessions should be available to read on leftsidebar even if I restart the application
3. When I go back to any chat history and start chatting it should retain the contextr and responses from model should be based on that
4. Task; come up with HLD and LLD
        HLD : high level application diagram
        LLD : db design , api design changes, how db will integrate in api



## python topics
1. Classes
2. Modules
3. List
4. Dict
5. Iterations over dict and lists
6. Rest api all methods - GET put, POST
7. how to call other modules
6. SQL queries

DB Design

1. chat_sessions
        id - UUID
        title
        created_at
        last_modified_at
        user_id
2. User
        id - UUID
        name
        email
3. Chat messages
        id - UUID
        text
        timestamp
        session_id
        user_id
        role [user,assistant]

1. User visits the platform
        if there is already sessions user can start chating into existing session
        else
        user click on new chat button
                1. UI will start new chat and asks user to type message
                2. when user click on send, message will be set to backend without any session id
                3. backend will assume no session id means creation of new message
                4. backend will store this message into chat table
                5. backend will make api call to llm
                6. LLM will respond, backend will store this respnse message also into chat table
                7. backend respond back to ui with response



When new session started
```mermaid 
sequenceDiagram
    actor User
    participant UI
    participant Backend
    participant DB as Chat Database
    participant LLM

    User->>UI: Click "New Chat"
    UI-->>User: Display empty chat screen

    User->>UI: Type message & click Send

    UI->>Backend: POST /chat<br/>(message only, optional sessionId, userid)

    Note over Backend: No sessionId received<br/>Treat as new conversation

    Backend->>DB: Create new chat/session<br/>Store user message
    DB-->>Backend: Chat saved (sessionId generated)

    Backend->>LLM: Send user message

    LLM-->>Backend: AI response

    Backend->>DB: Store AI response<br/>linked to sessionId

    DB-->>Backend: Response saved

    Backend-->>UI: Return sessionId + AI response

    UI-->>User: Display assistant response
```

When existing session used
``` mermaid
sequenceDiagram
    actor User
    participant UI
    participant Backend
    participant DB as Chat Database
    participant LLM

    User->>UI: Click "New Chat"
    UI-->>User: Display empty chat screen

    User->>UI: Type message & click Send

    UI->>Backend: POST /chat<br/>(message only, optional sessionId, userid)

    Note over Backend: existing sessionId received<br/>refer older message

    Backend->>DB: pull all messages from older chats for given session id
    DB-->>Backend: older chats returned

    Backend -->> Backend : prepend all prev messages to current message
    Backend->>LLM: Send current message+history of conversation

    LLM-->>Backend: AI response

    Backend->>DB: Store current user message + AI response<br/>linked to sessionId

    DB-->>Backend: Response saved

    Backend-->>UI: Return sessionId + AI response

    UI-->>User: Display assistant response
```





## 1st AUG
### Agenda:
1. session management harness
2. scaling the sessions
3. moving away from direct api to Open AI sdk
4. Understanding system prompt and role based prompt


=====================================================
1. Finish compaction api and recompaction
2. Try to pass compacted message to openai message
3. convert open ai api to Openai sdk
