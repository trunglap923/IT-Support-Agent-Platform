import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  failed: boolean;
}

export class AppErrorBoundary extends Component<Props, State> {
  state: State = { failed: false };

  static getDerivedStateFromError(): State {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Never render raw exceptions. This diagnostic stays in the local console
    // and can later be routed through the redacted observability adapter.
    console.error("Application render failed", error.name, info.componentStack);
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    return (
      <main className="route-fallback" role="alert">
        <p className="eyebrow">Đã xảy ra lỗi</p>
        <h1>Không thể hiển thị màn hình này</h1>
        <p>Hãy tải lại ứng dụng. Dữ liệu chưa gửi sẽ không được tự động xác nhận.</p>
        <button onClick={() => window.location.reload()} type="button">
          Tải lại
        </button>
      </main>
    );
  }
}
