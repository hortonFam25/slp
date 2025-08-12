/**
 * Logger utility for the application
 * Automatically disabled in production builds
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error';

interface LoggerOptions {
  prefix?: string;
  enabled?: boolean;
}

class Logger {
  private prefix: string;
  private enabled: boolean;

  constructor(options: LoggerOptions = {}) {
    this.prefix = options.prefix || '';
    this.enabled = options.enabled ?? import.meta.env.DEV;
  }

  private formatMessage(level: LogLevel, message: string, ...args: any[]): [string, ...any[]] {
    const timestamp = new Date().toISOString().split('T')[1].slice(0, -1);
    const prefixStr = this.prefix ? `[${this.prefix}] ` : '';
    const levelEmoji = this.getLevelEmoji(level);
    return [`${levelEmoji} ${timestamp} ${prefixStr}${message}`, ...args];
  }

  private getLevelEmoji(level: LogLevel): string {
    switch (level) {
      case 'debug': return '🐛';
      case 'info': return 'ℹ️';
      case 'warn': return '⚠️';
      case 'error': return '❌';
      default: return '📝';
    }
  }

  debug(message: string, ...args: any[]): void {
    if (this.enabled) {
      console.debug(...this.formatMessage('debug', message, ...args));
    }
  }

  info(message: string, ...args: any[]): void {
    if (this.enabled) {
      console.info(...this.formatMessage('info', message, ...args));
    }
  }

  warn(message: string, ...args: any[]): void {
    if (this.enabled) {
      console.warn(...this.formatMessage('warn', message, ...args));
    }
  }

  error(message: string, ...args: any[]): void {
    if (this.enabled) {
      console.error(...this.formatMessage('error', message, ...args));
    }
  }

  log(message: string, ...args: any[]): void {
    this.info(message, ...args);
  }

  // API-specific logging methods
  apiRequest(method: string, url: string): void {
    this.debug(`🚀 API Request: ${method.toUpperCase()} ${url}`);
  }

  apiResponse(status: number, url: string): void {
    this.debug(`✅ API Response: ${status} ${url}`);
  }

  apiError(status: number, message: string): void {
    this.error(`❌ API Error: ${status} ${message}`);
  }
}

// Create default logger instances
export const logger = new Logger();
export const apiLogger = new Logger({ prefix: 'API' });
export const componentLogger = new Logger({ prefix: 'Component' });

// Export the Logger class for creating custom loggers
export { Logger };

// Legacy console methods that are safe to use (they'll be removed in production by Vite)
export const devConsole = {
  log: (...args: any[]) => import.meta.env.DEV && console.log(...args),
  info: (...args: any[]) => import.meta.env.DEV && console.info(...args),
  warn: (...args: any[]) => import.meta.env.DEV && console.warn(...args),
  error: (...args: any[]) => import.meta.env.DEV && console.error(...args),
  debug: (...args: any[]) => import.meta.env.DEV && console.debug(...args),
};
