// FileName: commonFunc.ts

export function toErrorMessages(message: string | undefined): string[] {
  return message === undefined ? [] : [message];
}
