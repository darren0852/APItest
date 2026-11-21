const http = require("http");

const PORT = process.env.PORT || 9000;

const server = http.createServer((req, res) => {
  if (req.method === "POST" && req.url.includes("/chat/completions")) {
    let body = "";
    req.on("data", (chunk) => (body += chunk));
    req.on("end", () => {
      const isStream = body.includes('"stream":true') || body.includes('"stream": true');
      const modelMatch = body.match(/"model"\s*:\s*"([^"]+)"/);
      const model = modelMatch ? modelMatch[1] : "unknown";
      if (isStream) {
        res.writeHead(200, {
          "Content-Type": "text/event-stream",
          "Cache-Control": "no-cache",
          Connection: "keep-alive",
        });
        const chunks = ["Hello", " from", " mock", " provider"];
        chunks.forEach((c, i) => {
          const data = {
            id: `mock-${Date.now()}`,
            object: "chat.completion.chunk",
            model,
            choices: [{ index: 0, delta: i === 0 ? { role: "assistant", content: c } : { content: c }, finish_reason: i === chunks.length - 1 ? "stop" : null }],
          };
          res.write(`data: ${JSON.stringify(data)}\n\n`);
        });
        res.write("data: [DONE]\n\n");
        res.end();
      } else {
        res.writeHead(200, { "Content-Type": "application/json" });
        const resp = {
          id: `mock-${Date.now()}`,
          object: "chat.completion",
          model,
          usage: { prompt_tokens: 10, completion_tokens: 8, total_tokens: 18 },
          choices: [{ index: 0, message: { role: "assistant", content: "Hello from mock provider" }, finish_reason: "stop" }],
        };
        res.end(JSON.stringify(resp));
      }
    });
  } else {
    res.writeHead(404, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ error: "Not found" }));
  }
});

server.listen(PORT, () => console.log(`Mock provider running on port ${PORT}`));
