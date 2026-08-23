import { useInformationStore } from "../Store/informationStore";
import type {
  TypeExecutorInvokeCommand,
  TypeExecutorInvokeRequest,
  TypeExecutorInvokeResponse,
  TypeIpcArgs,
} from "../../../shared/ipc";

export async function invokeMain<C extends TypeExecutorInvokeCommand>(
  command: C,
  ...args: TypeIpcArgs<TypeExecutorInvokeRequest<C>>
): Promise<TypeExecutorInvokeResponse<C>> {
  const result = await window.executor.invoke(command, ...args);

  if (result.success === false) {
    const informationStore = useInformationStore();
    informationStore.showAlertMessage(result.error);
    throw new Error(result.error);
  }

  return result.data;
}
