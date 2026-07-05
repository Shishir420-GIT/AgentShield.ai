# Event System

Use an event bus.

Core events:
- PromptReceived
- ContextValidated
- PlannerValidated
- ToolAuthorized
- ToolExecuted
- OutputValidated
- MemoryUpdated
- IncidentCreated
- SessionClosed

Every event includes:
- correlation_id
- tenant_id
- session_id
- timestamp
