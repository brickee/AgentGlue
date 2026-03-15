/**
 * OpenClaw AgentGlue Plugin v0.2.0
 *
 * Bridges OpenClaw to the AgentGlue Python sidecar.
 * The sidecar wraps tools with AgentGlue middleware (dedup, rate limiting, etc.)
 */

import * as http from 'http';
import { spawn, ChildProcess } from 'child_process';
import * as path from 'path';

interface ToolParams {
  [key: string]: any;
}

interface SidecarConfig {
  host: string;
  port: number;
  autoStart: boolean;
  maxRestarts: number;
  restartDelayMs: number;
  healthCheckIntervalMs: number;
}

interface PluginContext {
  pluginDir: string;
  config?: Partial<SidecarConfig>;
}

class AgentGluePlugin {
  private config: SidecarConfig;
  private sidecarProcess: ChildProcess | null = null;
  private restartCount: number = 0;
  private healthCheckTimer: NodeJS.Timeout | null = null;
  private context: PluginContext | null = null;
  private isShuttingDown: boolean = false;

  constructor() {
    this.config = {
      host: '127.0.0.1',
      port: 8765,
      autoStart: true,
      maxRestarts: 3,
      restartDelayMs: 2000,
      healthCheckIntervalMs: 30000
    };
  }

  /**
   * Check if sidecar is healthy
   */
  private async healthCheck(): Promise<boolean> {
    return new Promise((resolve) => {
      const req = http.get(
        `http://${this.config.host}:${this.config.port}/health`,
        { timeout: 5000 },
        (res) => {
          let data = '';
          res.on('data', (chunk) => { data += chunk; });
          res.on('end', () => {
            try {
              const json = JSON.parse(data);
              resolve(json.status === 'ok');
            } catch {
              resolve(false);
            }
          });
        }
      );
      req.on('error', () => resolve(false));
      req.on('timeout', () => {
        req.destroy();
        resolve(false);
      });
    });
  }

  /**
   * Start the Python sidecar process
   */
  private async startSidecar(): Promise<void> {
    if (this.isShuttingDown) {
      throw new Error('Cannot start sidecar: plugin is shutting down');
    }

    if (this.sidecarProcess) {
      console.log('[AgentGlue] Sidecar already running');
      return;
    }

    if (!this.context) {
      throw new Error('Plugin context not available');
    }

    const sidecarPath = path.join(this.context.pluginDir, 'sidecar', 'server.py');
    console.log(`[AgentGlue] Starting sidecar: python3 ${sidecarPath}`);

    return new Promise((resolve, reject) => {
      this.sidecarProcess = spawn('python3', [sidecarPath, '--port', String(this.config.port)], {
        cwd: this.context!.pluginDir,
        detached: false,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      let stdout = '';
      let stderr = '';

      this.sidecarProcess.stdout?.on('data', (data) => {
        stdout += data.toString();
        console.log(`[Sidecar] ${data.toString().trim()}`);
      });

      this.sidecarProcess.stderr?.on('data', (data) => {
        stderr += data.toString();
        console.error(`[Sidecar Error] ${data.toString().trim()}`);
      });

      this.sidecarProcess.on('error', (err) => {
        console.error('[AgentGlue] Failed to start sidecar:', err.message);
        this.sidecarProcess = null;
        reject(err);
      });

      this.sidecarProcess.on('exit', (code, signal) => {
        console.log(`[AgentGlue] Sidecar exited (code: ${code}, signal: ${signal})`);
        this.sidecarProcess = null;

        if (!this.isShuttingDown && this.config.autoStart && this.restartCount < this.config.maxRestarts) {
          this.restartCount++;
          console.log(`[AgentGlue] Restarting sidecar (attempt ${this.restartCount}/${this.config.maxRestarts})...`);
          setTimeout(() => {
            this.startSidecar().catch(err => {
              console.error('[AgentGlue] Restart failed:', err.message);
            });
          }, this.config.restartDelayMs);
        }
      });

      // Wait for sidecar to be ready
      const checkReady = async () => {
        for (let i = 0; i < 30; i++) {
          await new Promise(r => setTimeout(r, 500));
          if (await this.healthCheck()) {
            console.log('[AgentGlue] Sidecar is healthy');
            this.restartCount = 0; // Reset restart counter on successful start
            resolve();
            return;
          }
        }
        reject(new Error('Sidecar failed to become healthy within 15 seconds'));
      };

      checkReady();
    });
  }

  /**
   * Stop the sidecar process gracefully
   */
  private async stopSidecar(): Promise<void> {
    if (!this.sidecarProcess) {
      return;
    }

    console.log('[AgentGlue] Stopping sidecar...');

    return new Promise((resolve) => {
      const timeout = setTimeout(() => {
        console.log('[AgentGlue] Force killing sidecar...');
        this.sidecarProcess?.kill('SIGKILL');
        resolve();
      }, 5000);

      this.sidecarProcess?.once('exit', () => {
        clearTimeout(timeout);
        this.sidecarProcess = null;
        resolve();
      });

      this.sidecarProcess?.kill('SIGTERM');
    });
  }

  /**
   * Start health check monitoring
   */
  private startHealthMonitoring(): void {
    if (this.healthCheckTimer) {
      return;
    }

    this.healthCheckTimer = setInterval(async () => {
      const healthy = await this.healthCheck();
      if (!healthy && !this.isShuttingDown && this.config.autoStart) {
        console.warn('[AgentGlue] Health check failed, sidecar may need restart');
      }
    }, this.config.healthCheckIntervalMs);
  }

  /**
   * Stop health check monitoring
   */
  private stopHealthMonitoring(): void {
    if (this.healthCheckTimer) {
      clearInterval(this.healthCheckTimer);
      this.healthCheckTimer = null;
    }
  }

  /**
   * Make HTTP request to Python sidecar
   */
  private async callSidecar(tool: string, params: ToolParams): Promise<any> {
    return new Promise((resolve, reject) => {
      const postData = JSON.stringify({ tool, params });
      
      const options = {
        hostname: this.config.host,
        port: this.config.port,
        path: '/call',
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Content-Length': Buffer.byteLength(postData)
        }
      };

      const req = http.request(options, (res) => {
        let data = '';
        res.on('data', (chunk) => { data += chunk; });
        res.on('end', () => {
          try {
            const json = JSON.parse(data);
            if (json.error) {
              reject(new Error(json.error));
            } else {
              resolve(json.result);
            }
          } catch (e) {
            reject(new Error(`Invalid JSON response: ${data}`));
          }
        });
      });

      req.on('error', (err) => {
        reject(new Error(`Sidecar connection failed: ${err.message}`));
      });

      req.write(postData);
      req.end();
    });
  }

  /**
   * Search tool - calls AgentGlue-wrapped search
   */
  async agentglue_search(params: { query: string }): Promise<string> {
    return this.callSidecar('search', params);
  }

  /**
   * Get metrics report from AgentGlue
   */
  async agentglue_metrics(_params: {}): Promise<string> {
    return this.callSidecar('metrics', {});
  }

  /**
   * Search files in a repository with deduplication
   */
  async deduped_search(params: {
    repo_path: string;
    pattern: string;
    file_pattern?: string;
    max_results?: number;
  }): Promise<string> {
    return this.callSidecar('deduped_search', params);
  }

  /**
   * Read file contents with deduplication and caching
   */
  async deduped_read_file(params: {
    file_path: string;
    offset?: number;
    limit?: number;
  }): Promise<string> {
    return this.callSidecar('deduped_read_file', params);
  }

  /**
   * List files in a directory with deduplication
   */
  async deduped_list_files(params: {
    dir_path: string;
    recursive?: boolean;
    include_hidden?: boolean;
  }): Promise<string> {
    return this.callSidecar('deduped_list_files', params);
  }

  /**
   * Get plugin health status
   */
  async agentglue_health(_params: {}): Promise<string> {
    const health = await this.getHealth();
    return JSON.stringify(health, null, 2);
  }

  /**
   * Plugin initialization - called by OpenClaw on load
   */
  async init(context: PluginContext): Promise<void> {
    console.log('[AgentGlue] Plugin initializing v0.2.0...');
    this.context = context;

    // Apply config overrides
    if (context.config) {
      this.config = { ...this.config, ...context.config };
    }

    // Auto-start sidecar if enabled
    if (this.config.autoStart) {
      // Check if sidecar already running
      const alreadyRunning = await this.healthCheck();
      if (alreadyRunning) {
        console.log('[AgentGlue] Sidecar already running (external)');
      } else {
        await this.startSidecar();
      }
      this.startHealthMonitoring();
    }

    console.log('[AgentGlue] Plugin initialized successfully');
  }

  /**
   * Plugin shutdown - called by OpenClaw on unload
   */
  async shutdown(): Promise<void> {
    console.log('[AgentGlue] Plugin shutting down...');
    this.isShuttingDown = true;
    this.stopHealthMonitoring();
    await this.stopSidecar();
    console.log('[AgentGlue] Plugin shutdown complete');
  }

  /**
   * Get plugin health status
   */
  async getHealth(): Promise<{ healthy: boolean; sidecarRunning: boolean; restarts: number }> {
    const sidecarRunning = await this.healthCheck();
    return {
      healthy: sidecarRunning,
      sidecarRunning,
      restarts: this.restartCount
    };
  }
}

// Export for OpenClaw loader
export default AgentGluePlugin;
export { AgentGluePlugin };
