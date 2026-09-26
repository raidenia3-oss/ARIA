import { auraService } from "./AURAService";

export interface AURANode {
  id: string;
  name: string;
  type: "audit" | "support" | "ame" | "godot";
  status: "online" | "offline" | "busy" | "error";
  cpu: number;
  lastSeen: number;
  capabilities: string[];
  autoRestart: boolean;
}

export class NodeController {
  private nodes: Map<string, AURANode> = new Map();
  private listeners: ((nodes: AURANode[]) => void)[] = [];

  constructor() {
    auraService.on("NODE_STATUS_UPDATE", (payload: any) => {
      this.updateNode(payload);
      this.notifyListeners();
    });
    auraService.on("NODE_LIST", (payload: any) => {
      payload.nodes?.forEach((n: AURANode) => this.nodes.set(n.id, n));
      this.notifyListeners();
    });
    auraService.on("connection", () => {
      auraService.send("GET_NODE_LIST", {});
    });
  }

  async activateNode(nodeId: string): Promise<void> {
    auraService.send("NODE_ACTIVATE", { node_id: nodeId });
    this.updateNodeStatus(nodeId, "busy");
  }

  async deactivateNode(nodeId: string): Promise<void> {
    auraService.send("NODE_DEACTIVATE", { node_id: nodeId });
    this.updateNodeStatus(nodeId, "offline");
  }

  async restartNode(nodeId: string): Promise<void> {
    auraService.send("NODE_RESTART", { node_id: nodeId });
    this.updateNodeStatus(nodeId, "busy");
  }

  async toggleAutoRestart(nodeId: string, value: boolean): Promise<void> {
    const node = this.nodes.get(nodeId);
    if (node) {
      node.autoRestart = value;
      this.nodes.set(nodeId, node);
      auraService.send("NODE_CONFIG", { node_id: nodeId, autoRestart: value });
    }
  }

  async runNodeTask(
    nodeId: string,
    task: string,
    args: Record<string, any> = {},
  ): Promise<void> {
    auraService.send("NODE_TASK", { node_id: nodeId, task, args });
  }

  getNodes(): AURANode[] {
    return Array.from(this.nodes.values());
  }
  getNode(id: string): AURANode | undefined {
    return this.nodes.get(id);
  }
  onNodesUpdate(cb: (nodes: AURANode[]) => void): void {
    this.listeners.push(cb);
  }

  private updateNode(data: Partial<AURANode> & { id: string }): void {
    const existing = this.nodes.get(data.id) || ({} as AURANode);
    this.nodes.set(data.id, { ...existing, ...data, lastSeen: Date.now() });
  }

  private updateNodeStatus(id: string, status: AURANode["status"]): void {
    const node = this.nodes.get(id);
    if (node) {
      node.status = status;
      this.nodes.set(id, node);
      this.notifyListeners();
    }
  }

  private notifyListeners(): void {
    this.listeners.forEach((cb) => cb(this.getNodes()));
  }
}

export const nodeController = new NodeController();
