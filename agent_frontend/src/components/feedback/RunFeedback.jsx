import { useMemo, useState } from 'react'
import { Check, MessageSquareText, ThumbsDown, ThumbsUp } from 'lucide-react'
import { AgentAPI } from '@/api/agentApi'

const REASONS = [
  ['wrong_recommendation', 'Đề xuất chưa phù hợp'],
  ['missing_context', 'Thiếu ngữ cảnh'],
  ['did_not_follow_request', 'Chưa làm đúng yêu cầu'],
  ['incorrect_facts', 'Thông tin chưa chính xác'],
  ['unsafe_or_inappropriate', 'Không an toàn hoặc không phù hợp'],
  ['too_slow', 'Xử lý quá lâu'],
  ['too_many_steps', 'Quá nhiều bước'],
  ['unclear_explanation', 'Giải thích chưa rõ'],
  ['review_or_approval_problem', 'Bước duyệt chưa hợp lý'],
  ['tool_or_system_error', 'Có lỗi hệ thống'],
  ['other', 'Lý do khác'],
]
const FEEDBACK_ENABLED = String(
  import.meta.env.VITE_RUN_FEEDBACK_ENABLED ?? 'true',
).toLowerCase() !== 'false'

const newSubmissionId = () => (
  globalThis.crypto?.randomUUID?.()
  || `feedback-${Date.now()}-${Math.random().toString(16).slice(2)}`
)

export default function RunFeedback({
  sessionId,
  targetKind = 'conversation',
  runId = null,
  requestId = null,
  surface,
  step = 4,
  workspaceRevision = null,
}) {
  const [sentiment, setSentiment] = useState(null)
  const [reasons, setReasons] = useState([])
  const [comment, setComment] = useState('')
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState('')
  const submissionId = useMemo(newSubmissionId, [])

  if (!FEEDBACK_ENABLED || !sessionId || !surface) return null

  const submit = async (value, selectedReasons = reasons) => {
    setError('')
    setStatus('submitting')
    try {
      await AgentAPI.submitFeedback({
        submission_id: submissionId,
        session_id: sessionId,
        target_kind: targetKind,
        run_id: targetKind === 'run' ? runId : null,
        request_id: requestId,
        sentiment: value,
        reason_codes: selectedReasons,
        comment,
        expected_behavior: '',
        surface,
        step,
        workspace_revision: workspaceRevision,
      })
      setSentiment(value)
      setStatus('saved')
    } catch (err) {
      setStatus('idle')
      setError(err.message || 'Không thể lưu phản hồi. Vui lòng thử lại.')
    }
  }

  const toggleReason = code => {
    setReasons(current => (
      current.includes(code)
        ? current.filter(value => value !== code)
        : [...current, code].slice(0, 5)
    ))
  }

  if (status === 'saved') {
    return (
      <div data-testid="run-feedback-saved" className="rounded-xl border border-green-200 bg-green-50 px-3 py-2 text-xs font-semibold text-green-700">
        <span className="inline-flex items-center gap-1.5"><Check className="h-3.5 w-3.5" /> Cảm ơn bạn. Phản hồi đã được ghi nhận.</span>
      </div>
    )
  }

  return (
    <section data-testid="run-feedback" className="rounded-xl border border-slate-200 bg-slate-50 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <MessageSquareText className="h-4 w-4 text-brand-600" />
          <p className="text-xs font-bold text-slate-800">Kết quả này có hữu ích không?</p>
        </div>
        <div className="flex gap-1.5">
          <button type="button" disabled={status === 'submitting'} onClick={() => submit('positive', [])}
            className="inline-flex items-center gap-1 rounded-lg border border-green-200 bg-white px-2.5 py-1.5 text-[11px] font-bold text-green-700 hover:bg-green-50 disabled:opacity-50">
            <ThumbsUp className="h-3.5 w-3.5" /> Có
          </button>
          <button type="button" disabled={status === 'submitting'} onClick={() => setSentiment('negative')}
            className="inline-flex items-center gap-1 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-[11px] font-bold text-slate-700 hover:border-red-200 hover:bg-red-50 hover:text-red-700 disabled:opacity-50">
            <ThumbsDown className="h-3.5 w-3.5" /> Chưa
          </button>
        </div>
      </div>

      {sentiment === 'negative' && (
        <div className="mt-3 border-t border-slate-200 pt-3">
          <p className="text-[11px] font-semibold text-slate-700">Điều gì cần cải thiện?</p>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {REASONS.map(([code, label]) => (
              <button key={code} type="button" onClick={() => toggleReason(code)}
                className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold transition ${reasons.includes(code) ? 'border-brand-400 bg-brand-50 text-brand-700' : 'border-slate-200 bg-white text-slate-600 hover:border-slate-300'}`}>
                {label}
              </button>
            ))}
          </div>
          <textarea value={comment} onChange={event => setComment(event.target.value.slice(0, 2000))}
            placeholder="Mô tả thêm (không bắt buộc nếu đã chọn lý do)"
            className="mt-2 min-h-16 w-full resize-y rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs outline-none focus:border-brand-400" />
          <button type="button" disabled={status === 'submitting' || (!reasons.length && !comment.trim())}
            onClick={() => submit('negative')}
            className="mt-2 rounded-lg bg-brand-600 px-3 py-1.5 text-[11px] font-bold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300">
            {status === 'submitting' ? 'Đang lưu…' : 'Gửi phản hồi'}
          </button>
        </div>
      )}
      {error && <p className="mt-2 text-[11px] font-medium text-red-600" role="alert">{error}</p>}
    </section>
  )
}
