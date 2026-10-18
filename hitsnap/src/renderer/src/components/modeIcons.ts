import { Bot, CalendarClock, CalendarDays, Dumbbell, Heart, ListChecks, Mic2, PartyPopper, Timer, Trophy, type LucideIcon } from 'lucide-react'
import type { GameMode } from '@/lib/game'

export const MODE_ICONS: Record<GameMode, LucideIcon> = {
  classic: Trophy,
  survival: Heart,
  blitz: Timer,
  quiz: ListChecks,
  artist: Mic2,
  year: CalendarClock,
  daily: CalendarDays,
  party: PartyPopper,
  practice: Dumbbell,
  duel: Bot
}
