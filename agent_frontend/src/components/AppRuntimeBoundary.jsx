import { Component } from 'react'
import { AlertTriangle, RefreshCw } from 'lucide-react'

export default class AppRuntimeBoundary extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('[AppRuntimeBoundary]', error, info)
  }

  render() {
    if (!this.state.error) return this.props.children

    return (
      <main className="grid min-h-screen place-items-center bg-slate-50 p-4">
        <section className="w-full max-w-lg rounded-3xl border border-amber-200 bg-white p-6 text-center shadow-xl" role="alert">
          <span className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-amber-50 text-amber-600">
            <AlertTriangle className="h-6 w-6" />
          </span>
          <h1 className="mt-4 text-lg font-black text-slate-900">Giao diện cần được tải lại</h1>
          <p className="mt-2 text-sm leading-6 text-slate-600">
            Phiên bản giao diện trên máy chủ vừa thay đổi hoặc một module chưa tải được. Dữ liệu campaign đã lưu không bị mất.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 inline-flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-brand-700"
          >
            <RefreshCw className="h-4 w-4" /> Tải lại giao diện
          </button>
        </section>
      </main>
    )
  }
}
