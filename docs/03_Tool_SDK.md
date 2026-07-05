# Tool SDK

Every capability is a Runtime Tool.

```python
class RuntimeTool:
    metadata: ToolMetadata

    async def execute(context):
        ...
```

Tool metadata:
- id
- version
- category
- priority
- dependencies
- capabilities

Return:
- evidence
- confidence
- severity
- recommendation
