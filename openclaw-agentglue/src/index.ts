/**
 * OpenClaw AgentGlue Plugin
 * 
 * Bridges OpenClaw to the AgentGlue Python sidecar.
 * The sidecar wraps tools with AgentGlue middleware (dedup, rate limiting, etc.)
 */

import * as http from 'http';

interface ToolParams {
  [key: string]: any;
}

interface SidecarConfig {
  host: string;
  port: number;
}

class AgentGluePlugin {
  private config: SidecarConfig;

  constructor() {
    this.config = {
      host: '127.0.0.1',
      port: 8765
    };
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
   * Plugin initialization - called by OpenClaw on load
   */
  async init(context: any): Promise<void> {
    console.log('[AgentGlue] Plugin initialized');
    // TODO: Auto-start sidecar if not running
  }

  /**
   * Plugin shutdown - called by OpenClaw on unload
   */
  async shutdown(): Promise<void> {
    console.log('[AgentGlue] Plugin shutting down');
    // TODO: Gracefully stop sidecar
  }
}

// Export for OpenClaw loader
export default AgentGluePlugin;
export { AgentGluePlugin };
