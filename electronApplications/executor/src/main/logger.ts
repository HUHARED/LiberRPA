// FileName: logger.ts
import path from "path";
import { format, transports, createLogger } from "winston";
import moment from "moment";

import { dictConfigBasic } from "./commonFunc";

const strLogPath = path.join(
  dictConfigBasic["outputLogPath"],
  "_Executor",
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
