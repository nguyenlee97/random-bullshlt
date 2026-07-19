import { CheckCircle2, ExternalLink, Link2, MessageCircleMore } from 'lucide-react'
import ZaloIcon from '@/components/ZaloIcon'

const ZALO_OA_URL = 'https://zalo.me/2224936774907333597'

export default function ZaloOACompanion({ identity, onOpenZaloOA }) {
  const providers = identity?.user?.providers || []
  const hasZaloLogin = providers.includes('zalo')
  const linked = Boolean(identity?.channels?.zalo_oa)
  const canLink = Boolean(
    identity?.authenticated
    && hasZaloLogin
    && identity?.auth_methods?.zalo_oa_link
    && !linked,
  )

  return (
    <aside
      data-testid="zalo-oa-companion"
      aria-labelledby="zalo-oa-companion-title"
      className="relative overflow-hidden rounded-3xl border border-[#b8d7ff] bg-gradient-to-br from-white via-[#f3f8ff] to-[#e7f1ff] p-4 shadow-[0_14px_40px_rgba(0,104,255,0.12)] sm:p-5 lg:sticky lg:top-6"
    >
      <div className="pointer-events-none absolute -right-10 -top-12 h-32 w-32 rounded-full bg-[#0068ff]/10 blur-2xl" />

      <div className="relative flex flex-col gap-5">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-3">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-[#0068ff] shadow-[0_10px_24px_rgba(0,104,255,0.25)]">
              <ZaloIcon className="h-8 w-8" />
            </span>
            <div>
              <p className="text-[10px] font-black uppercase tracking-[0.18em] text-[#0068ff]">Agent luôn bên bạn</p>
              <h2 id="zalo-oa-companion-title" className="mt-0.5 text-lg font-black leading-tight text-slate-900">
                Tiếp tục cùng Agent trên Zalo
              </h2>
            </div>
          </div>

          <p className="mt-3 text-sm leading-6 text-slate-600">
            Theo dõi OA để hỏi nhanh về trạng thái campaign, xem báo cáo và tiếp tục trao đổi dù bạn đang ở đâu.
          </p>

          <div className="mt-3 flex flex-wrap items-center gap-2">
            <a
              href={ZALO_OA_URL}
              target="_blank"
              rel="noreferrer"
              className="inline-flex items-center gap-1.5 rounded-xl bg-[#0068ff] px-3 py-2 text-xs font-bold text-white shadow-sm transition hover:bg-[#005ae0] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-200"
            >
              <MessageCircleMore className="h-3.5 w-3.5" />
              Mở Zalo OA
              <ExternalLink className="h-3 w-3" />
            </a>
            {canLink && (
              <button
                type="button"
                onClick={onOpenZaloOA}
                className="inline-flex items-center gap-1.5 rounded-xl border border-blue-200 bg-white px-3 py-2 text-xs font-bold text-[#0068ff] transition hover:bg-blue-50"
              >
                <Link2 className="h-3.5 w-3.5" /> Liên kết tài khoản
              </button>
            )}
            {linked && (
              <span className="inline-flex items-center gap-1.5 rounded-xl border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs font-bold text-emerald-700">
                <CheckCircle2 className="h-3.5 w-3.5" /> Đã liên kết
              </span>
            )}
          </div>
        </div>

        <a
          href={ZALO_OA_URL}
          target="_blank"
          rel="noreferrer"
          aria-label="Mở Zalo OA bằng mã QR"
          className="mx-auto flex w-full shrink-0 flex-col items-center rounded-2xl border border-blue-100 bg-white p-2 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-blue-200"
        >
          <img
            src="/zalo-oa-qr.jpg"
            alt="Mã QR theo dõi Zalo OA của Advertising Agent"
            className="h-32 w-32 rounded-xl object-cover"
          />
          <span className="mt-2 text-center text-[11px] font-bold text-slate-700">Quét mã để theo dõi OA</span>
        </a>
      </div>

      <p className="relative mt-3 text-[10px] leading-4 text-slate-500">
        Sau khi theo dõi, hãy liên kết tài khoản để Agent nhận đúng campaign của bạn.
      </p>
    </aside>
  )
}
