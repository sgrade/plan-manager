# Testing with MCP Inspector

See [https://github.com/modelcontextprotocol/inspector](https://github.com/modelcontextprotocol/inspector)

## CLI

Get tools
```sh
npx @modelcontextprotocol/inspector --cli http://host.docker.internal:3000/mcp --transport http --method tools/list
```

## Web UI

```sh
npx @modelcontextprotocol/inspector --config mcp.json --cli  --method tools/list
```
