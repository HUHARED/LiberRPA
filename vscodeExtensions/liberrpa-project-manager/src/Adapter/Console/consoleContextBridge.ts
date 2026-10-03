// FileName: consoleContextBridge.ts

import { randomUUID } from "node:crypto";
import { createServer, type Server, type Socket } from "node:net";

export interface ConsoleCredentialSnapshot {
  consoleUrl: string;
  token: string;
}

const STR_CONTEXT_REQUEST = "LIBERRPA_CONSOLE_CONTEXT_V1\n";
const INT_REQUEST_MAX_BYTES = 128;
const INT_SOCKET_TIMEOUT_MS = 3000;

export class ConsoleContextBridge {
  public readonly initialization: Promise<void>;
  private readonly pipeServer: Server;
  private readonly clientSockets = new Set<Socket>();
  private readonly pipePath = `\\\\.\\pipe\\LiberRPA-Console-editor-${randomUUID()}`;
  private listening = false;
  private disposed = false;

  public constructor(getCredentialSnapshot: () => ConsoleCredentialSnapshot | null) {
    this.pipeServer = createServer((clientSocket) => {
      this.clientSockets.add(clientSocket);
      clientSocket.setTimeout(INT_SOCKET_TIMEOUT_MS, () => clientSocket.destroy());
      clientSocket.on("error", () => clientSocket.destroy());
      clientSocket.on("close", () => this.clientSockets.delete(clientSocket));
      let requestBuffer = Buffer.alloc(0);
      let boolReplied = false;

      clientSocket.on("data", (requestChunk: Buffer) => {
        if (boolReplied) {
          clientSocket.destroy();
          return;
        }
        if (requestBuffer.length + requestChunk.length > INT_REQUEST_MAX_BYTES) {
          clientSocket.destroy();
          return;
        }
        requestBuffer = Buffer.concat([requestBuffer, requestChunk]);
        const strRequest = requestBuffer.toString("utf8");
        if (!STR_CONTEXT_REQUEST.startsWith(strRequest)) {
          clientSocket.destroy();
          return;
        }
        if (strRequest !== STR_CONTEXT_REQUEST) {
          return;
        }
        // The default Windows pipe ACL permits read-only access for some identities.
        // Require this write before returning credentials; never send on connection alone.
        boolReplied = true;
        const credentialSnapshot = getCredentialSnapshot();
        clientSocket.end(
          JSON.stringify({
            version: 1,
            context:
              credentialSnapshot === null
                ? null
                : { ...credentialSnapshot, clientType: "editor" },
          }) + "\n",
        );
      });
    });

    this.initialization = new Promise<void>((resolve, reject) => {
      if (process.platform !== "win32") {
        resolve();
        return;
      }
      this.pipeServer.on("error", () => {
        this.listening = false;
        reject(new Error("The local Console credential pipe could not be started."));
      });
      // Keep the operating system's default ACL; do not grant access to other users.
      this.pipeServer.listen(
        { path: this.pipePath, readableAll: false, writableAll: false },
        () => {
          if (this.disposed) {
            this.pipeServer.close();
          } else {
            this.listening = true;
          }
          resolve();
        },
      );
    });
  }

  public getEnvironment(): Record<string, string | undefined> {
    return {
      LIBERRPA_CONSOLE_PIPE: this.listening ? this.pipePath : undefined,
      LIBERRPA_CONSOLE_HOST_PID: this.listening ? String(process.pid) : undefined,
    };
  }

  public dispose(): void {
    this.disposed = true;
    this.listening = false;
    for (const clientSocket of this.clientSockets) {
      clientSocket.destroy();
    }
    if (this.pipeServer.listening) {
      this.pipeServer.close();
    }
  }
}
