import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import ProductDemo from '@/components/ProductDemo'

const DemoContext = createContext(null)

export function useDemo() {
  return useContext(DemoContext)
}

// Compatibility provider for the existing TopBar. The retired demo used live
// chat, DOM clicks and the real order button. This provider now opens the same
// deterministic sandbox used by the public landing page; it never calls the
// Agent API, mutates workspace state or dispatches campaign actions.
export function DemoProvider({ children, onActiveChange }) {
  const [mode, setMode] = useState(null)
  const startDemo = useCallback((requestedMode = 'copilot') => {
    setMode(requestedMode === 'autopilot' ? 'autopilot' : 'copilot')
  }, [])
  const stopDemo = useCallback(() => setMode(null), [])
  const value = useMemo(() => ({
    isActive: Boolean(mode),
    phase: mode ? 'SANDBOX' : 'IDLE',
    startDemo,
    stopDemo,
  }), [mode, startDemo, stopDemo])

  useEffect(() => {
    onActiveChange?.(Boolean(mode))
    return () => onActiveChange?.(false)
  }, [mode, onActiveChange])

  return (
    <DemoContext.Provider value={value}>
      {children}
      {mode && <ProductDemo mode={mode} onClose={stopDemo} />}
    </DemoContext.Provider>
  )
}
