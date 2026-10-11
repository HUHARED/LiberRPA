// FileName: ipc.ts

import { cloneJsonSerializable } from "../Common/json";
import { useInformationStore } from "../Store/informationStore";
import type {
  ExecutorInvokeCommand,
  ExecutorInvokeRequest,
  ExecutorInvokeResponse,
  TypeIpcArgs,
} from "../../../shared/ipc";

export async function invokeMain<C extends ExecutorInvokeCommand>(
  command: C,
  ...args: TypeIpcArgs<ExecutorInvokeRequest<C>>
): Promise<ExecutorInvokeResponse<C>> {
  const arrSerializableArg = args.map((arg: ExecutorInvokeRequest<C>) =>
    cloneJsonSerializable(arg),
  ) as TypeIpcArgs<ExecutorInvokeRequest<C>>;
  const result = await window.executor.invoke(command, ...arrSerializableArg);

  if (result.success === false) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(result.error);
    throw new Error(result.error);
  }

  return result.data;
}
