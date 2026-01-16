# **Technical Architecture & Stack Decisions**

This document outlines the architectural blueprint, technology selection, and critical engineering decisions for the GitHub MCP Productivity Engine.

## **1. High-Level Architecture**

The system follows a **Retrieval-Augmented Generation (RAG)** pattern where the "Retrieval" is performed dynamically by the Model Context Protocol (MCP) server rather than a static vector database.

### **Data Flow Sequence**

```mermaid
sequenceDiagram
    participant User as 👤 User (Frontend)
    participant Next as ⚛️ Next.js (Dashboard)
    participant API as 🐍 FastAPI (Orchestrator)
    participant DB as 🐘 PostgreSQL (Metrics Store)
    participant LLM as 🤖 LLM (Claude 3.5/GPT-4o)
    participant MCP as 🔌 GitHub MCP Server

    Note over User, API: Scenario: Interactive Chat Query
    User->>Next: "Why is deployment slow this week?"
    Next->>API: POST /chat {message, repo_id}
    API->>LLM: Prompt: "Analyze velocity. Tools available: [list_commits, ...]"
    LLM->>API: Tool Call: list_pull_requests(state='closed', last=7d)
    API->>MCP: Execute: list_pull_requests(...)
    MCP-->>API: Returns JSON (PR List)
    API->>LLM: Passes JSON data to context
    LLM-->>API: "Merge times increased by 40% due to large refactors."
    API-->>User: Returns natural language insight

