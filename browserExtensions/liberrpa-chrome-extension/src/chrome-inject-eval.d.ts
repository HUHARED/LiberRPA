// FileName: chrome-inject-eval.d.ts

declare module "chrome-inject-eval" {
  export function getEvalInstance(obj: any): (codeStr: string) => any;
  export function transformCode(codeStr: string): string;
}
