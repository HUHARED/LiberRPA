// FileName: startViteServer.ts
import { createServer } from "vite";
import getPort from "get-port";
import { loggerMain } from "./logger.js";

export async function startViteServer() {
  loggerMain.debug("--startViteServer--")
  const port = await getPort(); // Dynamically find an available port for open multiple windows.
  const server = await createServer({
    // Vite server options can be placed here
  });
  await server.listen(port);
  loggerMain.info(`Vite server is running on http://localhost:${port}`);

  return { url: `http://localhost:${port}`, server };
}
