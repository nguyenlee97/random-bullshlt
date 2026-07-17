import { useEffect, useState } from 'react'
import { Loader2, LockKeyhole, X } from 'lucide-react'

export default function AuthDialog({ open, mode = 'login', busy, error, onClose, onSubmit }) {
  const [activeMode, setActiveMode] = useState(mode)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')

  useEffect(() => {
    if (open) setActiveMode(mode)
    if (!open) {
      setEmail('')
      setPassword('')
      setDisplayName('')
    }
  }, [mode, open])

  if (!open) return null
  const registering = activeMode === 'register'
  const submit = event => {
    event.preventDefault()
    onSubmit({ mode: activeMode, email, password, displayName })
  }

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/45 p-4 backdrop-blur-sm" role="dialog" aria-modal="true" aria-labelledby="auth-title">
      <button type="button" className="absolute inset-0 cursor-default" onClick={busy ? undefined : onClose} aria-label="Đóng" />
      <form onSubmit={submit} className="relative w-full max-w-md rounded-3xl border border-slate-200 bg-white p-6 shadow-2xl">
        <button type="button" onClick={onClose} disabled={busy} className="absolute right-4 top-4 rounded-lg p-2 text-slate-400 hover:bg-slate-100" aria-label="Đóng">
          <X className="h-4 w-4" />
        </button>
        <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
          <LockKeyhole className="h-5 w-5" />
        </div>
        <h2 id="auth-title" className="mt-4 text-2xl font-black text-slate-900">{registering ? 'Tạo tài khoản' : 'Đăng nhập'}</h2>
        <p className="mt-2 text-sm leading-6 text-slate-600">Đăng nhập để lưu campaign vào tài khoản và tiếp tục trên thiết bị khác. Bạn vẫn có thể dùng ẩn danh.</p>

        <div className="mt-5 grid grid-cols-2 rounded-xl bg-slate-100 p-1 text-sm font-bold">
          {['login', 'register'].map(item => (
            <button key={item} type="button" onClick={() => setActiveMode(item)} disabled={busy}
              className={`rounded-lg px-3 py-2 ${activeMode === item ? 'bg-white text-brand-700 shadow-sm' : 'text-slate-500'}`}>
              {item === 'login' ? 'Đăng nhập' : 'Đăng ký'}
            </button>
          ))}
        </div>

        <div className="mt-5 space-y-4">
          {registering && (
            <label className="block text-sm font-semibold text-slate-700">
              Tên hiển thị
              <input value={displayName} onChange={event => setDisplayName(event.target.value)} required maxLength={80} autoComplete="name"
                className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100" />
            </label>
          )}
          <label className="block text-sm font-semibold text-slate-700">
            Email
            <input type="email" value={email} onChange={event => setEmail(event.target.value)} required maxLength={254} autoComplete="email"
              className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100" />
          </label>
          <label className="block text-sm font-semibold text-slate-700">
            Mật khẩu
            <input type="password" value={password} onChange={event => setPassword(event.target.value)} required minLength={10} maxLength={128}
              autoComplete={registering ? 'new-password' : 'current-password'}
              className="mt-1.5 w-full rounded-xl border border-slate-300 px-3.5 py-2.5 outline-none focus:border-brand-400 focus:ring-4 focus:ring-brand-100" />
            {registering && <span className="mt-1 block text-xs font-normal text-slate-500">Tối thiểu 10 ký tự.</span>}
          </label>
        </div>
        {error && <p className="mt-4 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">{error}</p>}
        <button type="submit" disabled={busy} className="mt-5 flex w-full items-center justify-center gap-2 rounded-xl bg-brand-500 px-4 py-3 text-sm font-bold text-white hover:bg-brand-600 disabled:cursor-wait disabled:opacity-70">
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {registering ? 'Tạo tài khoản và đăng nhập' : 'Đăng nhập'}
        </button>
      </form>
    </div>
  )
}
