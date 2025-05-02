// FileName: logger.ts
import path from "path";
import moment from "moment";
import { format, transports, createLogger } from "winston";

import { dictConfigBasic } from "./config";

export const strLogPath = path.join(
  dictConfigBasic["outputLogPath"],
  "_UiAnalyzer",
  `${moment().format("YYYY-MM-DD")}.log`
);

const logFormat = format.printf(({ level, message, timestamp }) => {
  return `[${timestamp}][${level.toUpperCase()}] ${message}`;
});

export const loggerMain = createLogger({
  format: format.combine(
    format.timestamp({
      format: () => moment().format("YYYY-MM-DD HH:mm:ss.SSS"),
    }),
    format.errors({ stack: true })
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
          return `${info.message}`;
        })
      ),
    }),
  ],
});
