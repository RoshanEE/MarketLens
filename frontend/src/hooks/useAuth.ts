// Hook that bootstraps Supabase auth and keeps the store in sync
import { useEffect } from 'react'
import { supabase } from '../services/supabase'
import { useAuthStore } from '../store/authStore'

export function useAuth() {
  const { setSession, ...state } = useAuthStore()

  useEffect(() => {
    // Load initial session
    supabase.auth.getSession().then(({ data }) => setSession(data.session))

    // Subscribe to future auth changes
    const { data: listener } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session)
    })

    return () => listener.subscription.unsubscribe()
  }, [setSession])

  return state
}
