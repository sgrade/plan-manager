# Testing with MCP Inspector

See [https://github.com/modelcontextprotocol/inspector](https://github.com/modelcontextprotocol/inspector)

## Prerequisites

Make sure you have the dependencies installed (it will be done automatically if you are in the devcontainer). 
Then. 

```sh
cd dev/mcp-inspector
```

## Web UI

```sh
npx @modelcontextprotocol/inspector --config mcp.json
```

## CLI

Get tools
```sh
npx @modelcontextprotocol/inspector --config mcp.json --cli  --method tools/list
```

List plans
```sh
npx @modelcontextprotocol/inspector --config mcp.json --cli  --method tools/call --tool-name list_plans
```