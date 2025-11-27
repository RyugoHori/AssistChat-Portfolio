/**
 * エラーバウンダリーコンポーネント
 * エラーを適切に処理する
 */

'use client';

import { Component, ReactNode } from 'react';
import { AlertCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';

interface ErrorBoundaryProps {
  children: ReactNode;
  fallback?: ReactNode;
}

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('ErrorBoundaryでエラーをキャッチしました:', error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <Card className="p-6 m-4">
          <div className="flex flex-col items-center justify-center gap-4 text-center">
            <AlertCircle className="h-12 w-12 text-red-500" />
            <div>
              <h3 className="text-lg font-semibold text-slate-900">
                エラーが発生しました
              </h3>
              <p className="text-sm text-slate-600 mt-2">
                予期しないエラーが発生しました。ページをリロードしてください。
              </p>
              {process.env.NODE_ENV === 'development' && this.state.error && (
                <pre className="mt-4 text-xs text-left bg-slate-100 p-3 rounded overflow-auto max-w-full">
                  {this.state.error.toString()}
                </pre>
              )}
            </div>
            <Button onClick={this.handleReset} variant="outline">
              再試行
            </Button>
          </div>
        </Card>
      );
    }

    return this.props.children;
  }
}