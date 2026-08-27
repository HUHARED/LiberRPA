// FileName: ipc.ts

import { useInformationStore } from "../Store/informationStore";
import type {
  Str_ExecutorInvokeCommand,
  Type_ExecutorInvoke_Request,
  Type_ExecutorInvoke_Response,
  TypeIpcArgs,
} from "../../../shared/ipc";

export async function invokeMain<C extends Str_ExecutorInvokeCommand>(
  command: C,
  ...args: TypeIpcArgs<Type_ExecutorInvoke_Request<C>>
): Promise<Type_ExecutorInvoke_Response<C>> {
  const result = await window.executor.invoke(command, ...args);

  if (result.success === false) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(result.error);
    throw new Error(result.error);
  }

  return result.data;
}
