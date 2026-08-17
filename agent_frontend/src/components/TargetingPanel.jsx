import { useState, useEffect, useCallback } from 'react'
import { ChevronDown, ChevronUp, Target, MapPin, Users, Smartphone, Tag, GraduationCap, Briefcase, DollarSign, Heart, Baby, Cloud, X } from 'lucide-react'
import { cn } from '@/lib/utils'

const ADVANCED_TARGETING_KEYS = [
  'marital', 'parental', 'education', 'income', 'career', 'interest', 'weather',
]

// ─── Fetch & cache targeting options from the real API ───────────────────────
const BACKEND_URL = (import.meta.env.VITE_BACKEND_URL || 'https://api.pawgrammers.io.vn').replace(/\/$/, '')
const TARGETING_API = `${BACKEND_URL}/api/targeting/options`
let _optionsCache = null
async function fetchTargetingOptions() {
  if (_optionsCache) return _optionsCache
  try {
    const res = await fetch(TARGETING_API, { signal: AbortSignal.timeout(5000) })
    if (!res.ok) throw new Error('API error')
    _optionsCache = await res.json()
  } catch {
    // Fallback schema
    _optionsCache = {
      geo: { 'Miền Bắc': ['Hà Nội','Hải Phòng','Bắc Ninh','Vĩnh Phúc','Quảng Ninh'], 'Miền Trung': ['Đà Nẵng','Huế','Nghệ An','Thanh Hóa'], 'Miền Nam': ['TP.HCM','Cần Thơ','Đồng Nai','Bình Dương'] },
      age: ['Under 18','18-24','25-34','35-44','45-54','55-64','Over 64'],
      gender: ['Male','Female'],
      deviceOS: ['Android','iOS','Windows Phone','PC and other'],
      deviceBrand: ['Samsung','Apple','Xiaomi','Oppo','Vivo','Realme','Huawei','ZTE'],
      marital: ['Single','Married'],
      parental: ['Have children under age 6','Have children','No children'],
      education: ['Entry Level','College & Bachelor','Master','Doctor'],
      income: ['Top 5%','Top 5-10%','Top 10-25%','Top 25-50%','Top 50-75%','Top 75-100%'],
      career: ['Student','Office Worker','Labour Worker','Housewife','Shop owner','Arts/Design/Entertainment','Sales','Healthcare'],
      interest: ['Real Estate','Entertainment > Movie','Entertainment > Celebrities','Travel','Sports','Fashion','F&B','Fintech','Education'],
      weather: ['Sunny','Rain','Cloudy','Other'],
    }
  }
  return _optionsCache
}

// ─── Helper: toggle a value in an array ──────────────────────────────────────
function toggleValue(arr = [], val) {
  return arr.includes(val) ? arr.filter(v => v !== val) : [...arr, val]
}

// ─── Section header ───────────────────────────────────────────────────────────
function SectionHeader({ icon: Icon, label, color = 'slate' }) {
  const colors = { slate: 'text-slate-500', blue: 'text-blue-500', violet: 'text-violet-500' }
  return (
    <div className={`flex items-center gap-1.5 mb-2 mt-3 first:mt-0`}>
      <Icon className={`w-3.5 h-3.5 flex-shrink-0 ${colors[color] || 'text-slate-500'}`} />
      <span className="text-[11px] font-bold text-slate-600 uppercase tracking-wider">{label}</span>
    </div>
  )
}

// ─── Multi-toggle chip row ─────────────────────────────────────────────────────
function ChipRow({ options, selected = [], onChange, compact = false, dimension = '' }) {
  return (
    <div className="flex flex-wrap gap-1">
      {options.map(opt => {
        const active = selected.includes(opt)
        return (
          <button
            key={opt}
            onClick={() => onChange(toggleValue(selected, opt))}
            data-demo="autopilot-targeting-option"
            data-targeting-dimension={dimension}
            data-targeting-value={opt}
            aria-pressed={active}
            className={cn(
              'px-2.5 py-1 rounded-lg border text-[11px] font-medium transition-all duration-100',
              active
                ? 'bg-brand-500 border-brand-500 text-white shadow-sm'
                : 'bg-white border-slate-200 text-slate-600 hover:border-brand-300 hover:text-brand-700',
              compact && 'py-0.5 text-[10px]'
            )}
          >
            {opt}
          </button>
        )
      })}
    </div>
  )
}

// ─── Location picker (grouped by region) ─────────────────────────────────────
function LocationPicker({ geoOptions, selected = [], onChange }) {
  const [search, setSearch] = useState('')

  const filtered = Object.entries(geoOptions || {}).reduce((acc, [region, cities]) => {
    const match = cities.filter(c => !search || c.toLowerCase().includes(search.toLowerCase()))
    if (match.length) acc[region] = match
    return acc
  }, {})

  return (
    <div className="flex gap-2 h-32">
      {/* Left: selectable list */}
      <div className="flex-1 border border-slate-200 rounded-lg overflow-hidden flex flex-col">
        <input
          value={search}
          onChange={e => setSearch(e.target.value)}
          placeholder="Tìm tỉnh/thành..."
          className="px-2 py-1.5 text-[11px] border-b border-slate-100 outline-none bg-white"
        />
        <div className="overflow-y-auto flex-1 py-1">
          {Object.entries(filtered).map(([region, cities]) => (
            <div key={region}>
              <div className="px-2 py-0.5 text-[10px] font-bold text-slate-400 uppercase">{region}</div>
              {cities.map(city => (
                <label key={city} className="flex items-center gap-2 px-3 py-0.5 hover:bg-slate-50 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={selected.includes(city)}
                    onChange={() => onChange(toggleValue(selected, city))}
                    className="w-3 h-3 accent-brand-500"
                  />
                  <span className="text-[11px] text-slate-700">{city}</span>
                </label>
              ))}
            </div>
          ))}
        </div>
      </div>
      {/* Right: selected locations */}
      <div className="w-36 border border-slate-200 rounded-lg flex flex-col">
        <div className="px-2 py-1 border-b border-slate-100 text-[10px] font-semibold text-slate-600">Đã chọn</div>
        <div className="overflow-y-auto flex-1 p-1">
          {selected.length === 0 ? (
            <p className="text-[10px] text-slate-400 text-center mt-3">Chưa chọn</p>
          ) : (
            <div className="flex flex-col gap-0.5">
              {selected.map(city => (
                <div key={city} className="flex items-center justify-between px-1.5 py-0.5 bg-brand-50 rounded text-[11px] text-brand-700">
                  <span className="truncate">{city}</span>
                  <button onClick={() => onChange(selected.filter(c => c !== city))} className="ml-1 text-brand-400 hover:text-brand-700 flex-shrink-0">
                    <X className="w-2.5 h-2.5" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ─── Count total selected values ─────────────────────────────────────────────
function countSelected(targeting) {
  return Object.values(targeting || {}).reduce((sum, arr) => sum + (Array.isArray(arr) ? arr.length : 0), 0)
}

// ─── Main TargetingForm ───────────────────────────────────────────────────────
export default function TargetingForm({ targeting = {}, onChange, autoExpand = false }) {
  const [expanded, setExpanded] = useState(autoExpand)
  const [opts, setOpts] = useState(null)
  const hasAdvancedSelection = ADVANCED_TARGETING_KEYS.some(
    key => Array.isArray(targeting[key]) && targeting[key].length > 0
  )
  const [advExpanded, setAdvExpanded] = useState(hasAdvancedSelection)

  // Autopilot opens AudienceStep for both audience and targeting repairs.
  // When the user explicitly chose "Chỉnh targeting", reveal the controls
  // immediately so they do not have to discover the collapsed panel first.
  useEffect(() => {
    if (autoExpand) setExpanded(true)
  }, [autoExpand])

  useEffect(() => {
    if (hasAdvancedSelection) setAdvExpanded(true)
  }, [hasAdvancedSelection])

  // Load options once
  useEffect(() => {
    if (expanded && !opts) {
      fetchTargetingOptions().then(setOpts)
    }
  }, [expanded, opts])

  const set = useCallback((key, val) => {
    onChange({ ...targeting, [key]: val })
  }, [targeting, onChange])

  const get = (key) => targeting[key.toLowerCase()] || targeting[key] || []

  const total = countSelected(targeting)

  return (
    <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
      {/* Collapsed header — always visible */}
      <button
        onClick={() => setExpanded(e => !e)}
        className="w-full flex items-center gap-2 px-3 py-2.5 hover:bg-slate-50 transition-colors text-left"
        data-demo="targeting-panel-toggle"
      >
        <Target className="w-4 h-4 text-slate-400 flex-shrink-0" />
        <span className="text-xs font-bold text-slate-600">Targeting Parameters</span>
        {total > 0 && (
          <span className="ml-1 px-1.5 py-0.5 rounded-full bg-brand-100 text-brand-700 text-[10px] font-semibold">
            {total} đã chọn
          </span>
        )}
        <span className="ml-auto text-[10px] text-slate-400">
          {expanded ? 'Thu gọn' : 'Mở rộng'}
        </span>
        {expanded
          ? <ChevronUp className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
          : <ChevronDown className="w-3.5 h-3.5 text-slate-400 flex-shrink-0" />
        }
      </button>

      {/* Summary chips when collapsed but has selections */}
      {!expanded && total > 0 && (
        <div className="px-3 pb-2 flex flex-wrap gap-1 border-t border-slate-50">
          {Object.entries(targeting).flatMap(([key, vals]) =>
            (Array.isArray(vals) ? vals : []).map(v => (
              <span key={`${key}-${v}`} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-[10px] font-medium border border-slate-200">
                {v}
                <button onClick={(e) => { e.stopPropagation(); set(key, get(key).filter(x => x !== v)) }}>
                  <X className="w-2 h-2" />
                </button>
              </span>
            ))
          )}
        </div>
      )}

      {/* Expanded form */}
      {expanded && (
        <div className="border-t border-slate-100 px-3 pb-3">
          {!opts ? (
            <div className="py-4 text-center text-xs text-slate-400 animate-pulse">Đang tải targeting options…</div>
          ) : (
            <>
              {/* ── DEMOGRAPHICS ─────────────────────────────────── */}
              <div className="mt-3 mb-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100 pb-1">
                Demographics
              </div>

              {/* Location */}
              <SectionHeader icon={MapPin} label="Địa lý" color="blue" />
              <LocationPicker
                geoOptions={opts.geo}
                selected={get('geo')}
                onChange={v => set('geo', v)}
              />

              {/* Age */}
              <SectionHeader icon={Users} label="Độ tuổi" />
              <ChipRow dimension="age" options={opts.age} selected={get('age')} onChange={v => set('age', v)} />

              {/* Gender */}
              <SectionHeader icon={Users} label="Giới tính" />
              <ChipRow dimension="gender" options={opts.gender} selected={get('gender')} onChange={v => set('gender', v)} />

              {/* Device OS */}
              <SectionHeader icon={Smartphone} label="Device OS" />
              <ChipRow dimension="deviceOS" options={opts.deviceOS} selected={get('deviceOS')} onChange={v => set('deviceOS', v)} />

              {/* Device Brand */}
              <SectionHeader icon={Smartphone} label="Device Brand" />
              <ChipRow dimension="deviceBrand" options={opts.deviceBrand} selected={get('deviceBrand')} onChange={v => set('deviceBrand', v)} compact />

              {/* ── ADVANCED TARGETING ───────────────────────────── */}
              <button
                onClick={() => setAdvExpanded(e => !e)}
                className="w-full flex items-center gap-2 mt-3 py-1.5 text-left"
                data-demo="advanced-targeting-toggle"
              >
                <div className="flex-1 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-t border-slate-100 pt-1.5">
                  Advanced Targeting
                </div>
                {advExpanded ? <ChevronUp className="w-3 h-3 text-slate-400" /> : <ChevronDown className="w-3 h-3 text-slate-400" />}
              </button>

              {advExpanded && (
                <>
                  <SectionHeader icon={Heart} label="Tình trạng hôn nhân" />
                  <ChipRow dimension="marital" options={opts.marital} selected={get('marital')} onChange={v => set('marital', v)} />

                  <SectionHeader icon={Baby} label="Tình trạng con cái" />
                  <ChipRow dimension="parental" options={opts.parental} selected={get('parental')} onChange={v => set('parental', v)} compact />

                  <SectionHeader icon={GraduationCap} label="Học vấn" />
                  <ChipRow dimension="education" options={opts.education} selected={get('education')} onChange={v => set('education', v)} />

                  <SectionHeader icon={DollarSign} label="Thu nhập" />
                  <ChipRow dimension="income" options={opts.income} selected={get('income')} onChange={v => set('income', v)} compact />

                  <SectionHeader icon={Briefcase} label="Nghề nghiệp" />
                  <ChipRow dimension="career" options={opts.career} selected={get('career')} onChange={v => set('career', v)} compact />

                  <SectionHeader icon={Tag} label="Sở thích" />
                  <ChipRow dimension="interest" options={opts.interest} selected={get('interest')} onChange={v => set('interest', v)} compact />

                  <SectionHeader icon={Cloud} label="Thời tiết" />
                  <ChipRow dimension="weather" options={opts.weather} selected={get('weather')} onChange={v => set('weather', v)} />
                </>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
