// FileName: consoleAccount.ts

export enum ConsoleConnection {
  SignedOut = "signed_out",
  SelectingExecutor = "selecting_executor",
  Connected = "connected",
  Reconnecting = "reconnecting",
  AccessUnavailable = "access_unavailable",
}

export enum ConsoleDepartmentRole {
  Developer = "developer",
  Operator = "operator",
}

export interface ConsoleDepartmentInfo {
  id: string;
  name: string;
  path: string;
  role: ConsoleDepartmentRole | null;
}

export interface ConsoleSessionInfo {
  session: { id: string; selection_required: boolean; expires_at: string };
  user: { id: string; email: string; username: string };
  organization: { id: string; name: string };
  is_org_admin: boolean;
  account_departments: ConsoleDepartmentInfo[];
  executor: {
    id: string;
    name: string;
    department_id: string;
    dispatch_enabled: boolean;
  } | null;
  last_seen_at: string | null;
  heartbeat_interval_seconds: number;
}

export interface ConsoleExecutorChoice {
  id: string;
  name: string;
  department: { id: string; name: string; path: string };
  dispatch_enabled: boolean;
}

export interface ConsoleExecutorPage {
  executors: ConsoleExecutorChoice[];
  page: number;
  total_pages: number;
}

export interface ConsoleSignInArgs {
  email: string;
  password: string;
}

export interface ConsoleAccountState {
  consoleUrl: string;
  connection: ConsoleConnection;
  sessionInfo: ConsoleSessionInfo | null;
  message: string;
  hasCredential: boolean;
  hasActiveRun: boolean;
  busy: boolean;
}
