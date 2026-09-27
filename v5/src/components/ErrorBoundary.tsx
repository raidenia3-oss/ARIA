// Error boundary component for React 19
// Fase 57.5: Catches rendering errors and shows fallback UI
import React, { Component, ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  override componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('[ErrorBoundary] Caught error:', error, errorInfo);
    // Send to backend for logging
    fetch('/api/system/log', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        level: 'error',
        message: error.message,
        stack: error.stack,
        componentStack: errorInfo.componentStack,
      }),
    }).catch(() => {});
  }

  override render() {
    if (this.state.hasError) {
      return this.props.fallback || (
        <div className="flex min-h-[200px] flex-col items-center justify-center rounded-2xl bg-red-500/10 p-6 text-center">
          <span className="text-4xl">⚠️</span>
          <h3 className="mt-2 text-lg font-semibold text-red-400">Algo salió mal</h3>
          <p className="mt-1 text-sm text-red-300/70">
            {this.state.error?.message || 'Error desconocido'}
          </p>
          <button
            onClick={() => this.setState({ hasError: false, error: null })}
            className="mt-3 rounded-lg bg-red-500/20 px-4 py-2 text-sm text-red-300 hover:bg-red-500/30"
          >
            Reintentar
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}