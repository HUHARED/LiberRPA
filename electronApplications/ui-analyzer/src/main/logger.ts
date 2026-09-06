// FileName: logger.ts

import fs from "fs";
import path from "path";
import moment from "moment";
import { createLogger, format, transports, type Logger } from "winston";

export function createMainLogger(strOutputLogFolderPath: string): Logger {
  const strLogPath = path.join(
    strOutputLogFolderPath,
    "_UiAnalyzer",
    `${moment().format("YYYY-MM-DD")}.log`,
  );
  fs.mkdirSync(path.dirname(strLogPath), { recursive: true });

  const logFormat = format.printf(({ level, message, timestamp }) => {
    return `[${timestamp}][${level.toUpperCase()}] ${String(message)}`;
  });

  return createLogger({
    format: format.combine(
      format.timestamp({
        format: () => moment().format("YYYY-MM-DD HH:mm:ss.SSS"),
      }),
      format.errors({ stack: true }),
    ),
    transports: [
      new transports.File({
        filename: strLogPath,
        level: "debug",
        format: logFormat,
      }),
      new transports.Console({
        level: "debug",
        format: format.combine(
          format.colorize(),
          format.printf((info) => {
            return `${String(info.message)}`;
          }),
        ),
      }),
    ],
  });
}
